const pageContent=document.getElementById("pageContent");
const creationData=JSON.parse(document.getElementById("job-creation-data").textContent);
const csrfToken=document.cookie.split("; ").find(row=>row.startsWith("csrftoken="))?.split("=")[1]||"";
const escapeHtml=value=>String(value??"").replace(/[&<>"']/g,character=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
const endpoint=window.location.pathname;
const workflowOptions=creationData.workflows||[];
const manualWorkflow=workflowOptions.find(workflow=>workflow.slug==="manual");
let details=creationData.draft?{...creationData.draft}:{};
let draftId=creationData.draft?.id||null;
let selectedWorkflowId=manualWorkflow?.id||"";
let threshold="70";
let criteria=[];
let criterionName="";
let requirementDraft=[];
let criterionComposerOpen=false;
let nextId=1;

function renderFrame(content){
  pageContent.innerHTML=`
    <style>
      .job-create{max-width:980px;margin:0 auto;}
      .job-create-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:20px;}
      .job-create-head h1{margin:0;font-size:27px;}
      .job-create-head p{margin:5px 0 0;color:var(--muted);}
      .job-create-steps{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:11px;white-space:nowrap;}
      .job-create-steps span{display:flex;align-items:center;gap:7px;}
      .job-create-steps b{width:23px;height:23px;border:1px solid var(--line);border-radius:50%;display:grid;place-items:center;font-size:10px;}
      .job-create-steps .active{color:var(--blue);font-weight:700;}
      .job-create-steps .active b{border-color:var(--blue);background:#eef3ff;}
      .job-create-separator{width:30px;border-top:1px solid var(--line);}
      .job-create-panel{background:#fff;border:1px solid var(--line);padding:24px;}
      .job-create-panel h2{margin:0;font-size:17px;}
      .job-create-panel>p{margin:5px 0 20px;color:var(--muted);font-size:11px;}
      .job-create-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
      .job-create-field{display:grid;gap:6px;color:var(--text);font-size:11px;font-weight:650;}
      .job-create-field input,.job-create-field textarea,.job-create-field select{width:100%;min-width:0;border:1px solid var(--line);padding:10px 11px;background:#fff;font:inherit;font-weight:400;}
      .job-create-field textarea{min-height:120px;resize:vertical;line-height:1.5;}
      .job-create-field.full{grid-column:1/-1;}
      .job-create-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:22px;padding-top:16px;border-top:1px solid var(--line);}
      .job-create-actions-right{display:flex;gap:8px;}
      .job-create-actions button{min-height:38px;}
      .job-create-error{display:none;margin-top:14px;padding:10px 12px;border-left:3px solid var(--red);background:var(--redbg);color:var(--red);font-size:11px;}
      .job-create-error.show{display:block;}
      .job-create-workflow{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:end;padding:16px;background:#f8fafc;border:1px solid var(--line);margin-bottom:18px;}
      .job-create-threshold[hidden]{display:none;}
      .job-create-threshold-row{display:flex;gap:8px;align-items:center;}
      .job-create-threshold-row input{width:120px;}
      .job-create-threshold-row span{color:var(--muted);font-size:12px;}
      .job-create-criteria-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:22px 0 12px;}
      .job-create-criteria-head h2{font-size:15px;margin:0;}
      .job-create-criterion{border:1px solid var(--line);margin-top:12px;padding:16px;}
      .job-create-criterion-head{display:flex;align-items:flex-end;gap:10px;}
      .job-create-criterion-head .job-create-field{flex:1;}
      .job-create-requirements{display:grid;gap:10px;margin-top:14px;}
      .job-create-requirement{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:end;padding-top:10px;border-top:1px solid #edf0f2;}
      .job-create-required{height:38px;display:flex;align-items:center;gap:6px;color:var(--muted);font-size:10px;white-space:nowrap;}
      .job-create-required input{accent-color:var(--blue);}
      .job-create-requirement-entry{display:flex;align-items:stretch;margin-top:14px;}
      .job-create-requirement-entry input{flex:1;min-width:0;height:40px;border:1px solid var(--line);padding:0 11px;font:inherit;font-size:11px;}
      .job-create-requirement-entry button{min-width:78px;border:1px solid var(--blue);background:var(--blue);color:#fff;font-size:10px;font-weight:700;}
      .job-create-requirement-entry button:disabled{border-color:var(--line);background:#eef0f2;color:#9199a2;cursor:not-allowed;}
      .job-create-requirement-help{margin:5px 0 0;color:var(--muted);font-size:9px;}
      .job-create-pending-list{display:grid;gap:7px;margin-top:12px;}
      .job-create-pending-row{display:flex;align-items:center;gap:10px;padding:9px 10px;background:#f7f9fa;border:1px solid var(--line);}
      .job-create-pending-row>span{flex:1;font-size:10px;line-height:1.45;}
      .job-create-pending-row button,.job-create-saved-actions button{border:0;background:none;color:var(--blue);font-size:10px;font-weight:650;}
      .job-create-save-criterion{margin-top:14px;}
      .job-create-saved-criterion{border:1px solid var(--line);padding:14px;margin-top:10px;}
      .job-create-saved-head{display:flex;justify-content:space-between;align-items:center;gap:12px;}
      .job-create-saved-head strong{font-size:12px;}
      .job-create-saved-actions{display:flex;gap:10px;}
      .job-create-saved-criterion ul{margin:10px 0 0;padding-left:18px;color:var(--muted);font-size:10px;line-height:1.7;}
      .job-create-review-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
      .job-create-review-item{padding:12px;background:#f7f9fa;border:1px solid var(--line);}
      .job-create-review-item.full{grid-column:1/-1;}
      .job-create-review-item small{display:block;margin-bottom:3px;color:var(--muted);font-size:9px;text-transform:uppercase;}
      .job-create-review-item strong{font-size:11px;overflow-wrap:anywhere;}
      .job-create-review-description{white-space:pre-wrap;line-height:1.55;font-weight:400!important;}
      .job-create-review-criteria{margin-top:18px;}
      .job-create-review-criteria h3{font-size:13px;margin:0 0 10px;}
      @media(max-width:700px){.job-create-review-grid{grid-template-columns:1fr}}
      .job-create-empty{padding:28px 16px;border:1px dashed var(--line);text-align:center;color:var(--muted);font-size:11px;}
      @media(max-width:700px){.job-create-head{align-items:flex-start;flex-direction:column}.job-create-panel{padding:18px}.job-create-grid,.job-create-workflow{grid-template-columns:1fr}.job-create-field.full{grid-column:auto}.job-create-requirement{grid-template-columns:1fr auto}.job-create-required{grid-column:1}.job-create-requirement [data-remove-requirement]{grid-column:2;grid-row:1/3}}
    </style>
    <div class="job-create">
      <div class="job-create-head">
        <div><p class="eyebrow">HIRING WORKSPACE</p><h1>Create a job</h1><p>Set up the role, define how candidates are assessed, then publish.</p></div>
        <div class="job-create-steps"><span class="${content.stage===1?"active":""}"><b>1</b> Job details</span><i class="job-create-separator"></i><span class="${content.stage===2?"active":""}"><b>2</b> Criteria & workflow</span><i class="job-create-separator"></i><span class="${content.stage===3?"active":""}"><b>3</b> Review</span></div>
      </div>
      ${content.body}
    </div>`;
}

function showError(message){
  const errorBox=document.getElementById("job-create-error");
  if(!errorBox)return;
  errorBox.textContent=message;
  errorBox.classList.add("show");
}

async function postAction(payload){
  const response=await fetch(endpoint,{
    method:"POST",
    headers:{"Content-Type":"application/json","X-CSRFToken":csrfToken,"Accept":"application/json"},
    body:JSON.stringify(payload),
  });
  const result=await response.json().catch(()=>({}));
  if(!response.ok){
    const formErrors=result.errors?Object.values(result.errors).flat().map(error=>error.message).join(" "):"";
    throw new Error(formErrors||result.error||"The request could not be completed.");
  }
  return result;
}

function renderDetails(){
  renderFrame({stage:1,body:`
    <form class="job-create-panel" id="job-details-form" novalidate>
      <h2>Job details</h2><p>Enter the role information candidates will see.</p>
      <div class="job-create-grid">
        <label class="job-create-field">Job title<input name="title" value="${escapeHtml(details.title||"")}" required maxlength="100" placeholder="e.g. Senior Product Designer"></label>
        <label class="job-create-field">Location<input name="location" value="${escapeHtml(details.location||"")}" required maxlength="100" placeholder="e.g. Port Moresby, Hybrid"></label>
        <label class="job-create-field">Salary<input name="salary" type="number" min="0" step="0.01" value="${escapeHtml(details.salary||"")}" required placeholder="e.g. 85000"></label>
        <label class="job-create-field">Application deadline<input name="deadline" type="datetime-local" value="${escapeHtml(details.deadline||"")}" required></label>
        <label class="job-create-field full">Job description<textarea name="description" required placeholder="Describe the role, responsibilities, and experience needed.">${escapeHtml(details.description||"")}</textarea></label>
      </div>
      <div class="job-create-error" id="job-create-error" role="alert"></div>
      <div class="job-create-actions"><a class="textbtn" href="/dashboard/jobs/">Cancel</a><button class="primary" type="submit">Next: criteria & workflow →</button></div>
    </form>`});

  document.getElementById("job-details-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const form=event.currentTarget;
    if(!form.reportValidity())return;
    const nextButton=form.querySelector('button[type="submit"]');
    nextButton.disabled=true;
    details=Object.fromEntries(new FormData(form));
    try{
      const result=await postAction({action:"save_job_details",...details});
      draftId=result.job_id;
      renderWorkflowAndCriteria();
    }catch(error){showError(error.message);}
    finally{nextButton.disabled=false;}
  });
}

function renderCriteriaList(){
  return criteria.length?criteria.map(criterion=>`<section class="job-create-saved-criterion">
    <div class="job-create-saved-head"><strong>${escapeHtml(criterion.name)}</strong><div class="job-create-saved-actions"><button type="button" data-edit-criterion="${criterion.id}">Edit</button><button type="button" data-remove-criterion="${criterion.id}">Remove</button></div></div>
    <ul>${criterion.requirements.map(requirement=>`<li>${escapeHtml(requirement.description)}${requirement.required?" · Required":""}</li>`).join("")}</ul>
  </section>`).join(""):`<div class="job-create-empty">No criteria saved yet. Add at least one criterion and its requirements.</div>`;
}

function renderWorkflowAndCriteria(message=""){
  const workflow=workflowOptions.find(item=>String(item.id)===String(selectedWorkflowId));
  const isAuto=workflow?.slug==="auto";
  const workflowMarkup=workflowOptions.map(item=>`<option value="${item.id}" data-slug="${escapeHtml(item.slug)}" ${String(item.id)===String(selectedWorkflowId)?"selected":""}>${item.slug==="auto"?"Fully Automated":"Semi Automated"}</option>`).join("");
  const pendingRequirements=requirementDraft.map(requirement=>`<div class="job-create-pending-row"><span>${escapeHtml(requirement.description)}</span><label class="job-create-required"><input type="checkbox" data-required-id="${requirement.id}" ${requirement.required?"checked":""}> Required</label><button type="button" data-remove-draft-requirement="${requirement.id}" aria-label="Remove requirement">Remove</button></div>`).join("");
  const criterionComposer=criterionComposerOpen?`<section class="job-create-criterion">
    <label class="job-create-field">Criterion name<input id="criterion-name" value="${escapeHtml(criterionName)}" placeholder="e.g. Relevant experience" required></label>
    <div class="job-create-requirement-entry"><input id="new-requirement" placeholder="Type a requirement, then add it" aria-label="New requirement"><button type="button" id="add-requirement" disabled>Add</button></div>
    <p class="job-create-requirement-help">Add requirements one at a time. You can mark each one as required.</p>
    <div class="job-create-pending-list">${pendingRequirements}</div>
    <button type="button" class="primary job-create-save-criterion" id="save-criterion" ${!criterionName.trim()||!requirementDraft.length?"disabled":""}>Save criterion</button>
  </section>`:`<button type="button" class="secondary" id="add-criterion">+ Add criterion</button>`;

  renderFrame({stage:2,body:`
    <section class="job-create-panel">
      <h2>Criteria & workflow</h2><p>Set the application workflow and define criteria before reviewing the job.</p>
      <div class="job-create-workflow">
        <label class="job-create-field">Application workflow<select id="creation-workflow">${workflowMarkup}</select></label>
        <label class="job-create-field job-create-threshold" ${isAuto?"":"hidden"}>AI shortlisting threshold<div class="job-create-threshold-row"><input id="creation-threshold" type="number" min="0" max="100" step="1" value="${escapeHtml(threshold)}" ${isAuto?"required":"disabled"}><span>out of 100</span></div></label>
      </div>
      <div class="job-create-criteria-head"><h2>Job criteria</h2>${criterionComposerOpen?"":criterionComposer}</div>
      <div id="criteria-list">${renderCriteriaList()}${criterionComposerOpen?criterionComposer:""}</div>
      <div class="job-create-error ${message?"show":""}" id="job-create-error" role="alert">${escapeHtml(message)}</div>
      <div class="job-create-actions"><button type="button" class="secondary" id="back-to-details">← Back</button><button type="button" class="primary" id="review-job" ${criteria.length===0||criterionComposerOpen?"disabled":""}>Review and publish →</button></div>
    </section>`});

  document.getElementById("creation-workflow").addEventListener("change",event=>{
    selectedWorkflowId=event.target.value;
    const auto=event.target.selectedOptions[0]?.dataset.slug==="auto";
    const thresholdField=document.querySelector(".job-create-threshold");
    const thresholdInput=document.getElementById("creation-threshold");
    thresholdField.hidden=!auto;
    thresholdInput.disabled=!auto;
    thresholdInput.required=auto;
    if(auto&&!thresholdInput.value)thresholdInput.value=threshold;
  });
  document.getElementById("creation-threshold").addEventListener("input",event=>{threshold=event.target.value;});
  document.getElementById("add-criterion")?.addEventListener("click",()=>{
    criterionName="";
    requirementDraft=[];
    criterionComposerOpen=true;
    renderWorkflowAndCriteria();
    document.getElementById("criterion-name")?.focus();
  });
  document.getElementById("criterion-name")?.addEventListener("input",event=>{
    criterionName=event.target.value;
    const saveButton=document.getElementById("save-criterion");
    if(saveButton)saveButton.disabled=!criterionName.trim()||!requirementDraft.length;
  });
  const requirementInput=document.getElementById("new-requirement");
  const addRequirementButton=document.getElementById("add-requirement");
  requirementInput?.addEventListener("input",()=>{addRequirementButton.disabled=!requirementInput.value.trim();});
  requirementInput?.addEventListener("keydown",event=>{
    if(event.key==="Enter"){event.preventDefault();if(!addRequirementButton.disabled)addRequirementButton.click();}
  });
  addRequirementButton?.addEventListener("click",()=>{
    const description=requirementInput.value.trim();
    if(!description)return;
    requirementDraft.push({id:nextId++,description,required:true});
    renderWorkflowAndCriteria();
    document.getElementById("new-requirement")?.focus();
  });
  document.getElementById("criteria-list").addEventListener("click",event=>{
    const removeDraft=event.target.closest("[data-remove-draft-requirement]");
    const removeSaved=event.target.closest("[data-remove-criterion]");
    const editSaved=event.target.closest("[data-edit-criterion]");
    if(removeDraft){
      requirementDraft=requirementDraft.filter(item=>item.id!==Number(removeDraft.dataset.removeDraftRequirement));
      renderWorkflowAndCriteria();
    }else if(removeSaved){
      criteria=criteria.filter(item=>item.id!==Number(removeSaved.dataset.removeCriterion));
      renderWorkflowAndCriteria();
    }else if(editSaved){
      const criterion=criteria.find(item=>item.id===Number(editSaved.dataset.editCriterion));
      criterionName=criterion.name;
      requirementDraft=criterion.requirements.map(item=>({...item}));
      criteria=criteria.filter(item=>item.id!==criterion.id);
      criterionComposerOpen=true;
      renderWorkflowAndCriteria();
      document.getElementById("criterion-name")?.focus();
    }
  });
  document.getElementById("criteria-list").addEventListener("change",event=>{
    const requiredInput=event.target.closest("[data-required-id]");
    if(requiredInput){
      const requirement=requirementDraft.find(item=>item.id===Number(requiredInput.dataset.requiredId));
      if(requirement)requirement.required=requiredInput.checked;
    }
  });
  document.getElementById("save-criterion")?.addEventListener("click",()=>{
    criterionName=document.getElementById("criterion-name").value.trim();
    if(!criterionName||!requirementDraft.length)return;
    criteria.push({id:nextId++,name:criterionName,requirements:requirementDraft.map(item=>({...item}))});
    criterionName="";
    requirementDraft=[];
    criterionComposerOpen=false;
    renderWorkflowAndCriteria();
  });
  document.getElementById("back-to-details").addEventListener("click",renderDetails);
  document.getElementById("review-job").addEventListener("click",()=>{
    if(!criteria.length||criterionComposerOpen)return;
    if(!selectedWorkflowId){showError("Choose a job workflow before continuing.");return;}
    const currentWorkflow=workflowOptions.find(item=>String(item.id)===String(selectedWorkflowId));
    if(currentWorkflow?.slug==="auto"&&(!Number.isInteger(Number(threshold))||Number(threshold)<0||Number(threshold)>100)){showError("Enter an AI threshold from 0 to 100.");return;}
    renderReview();
  });
}

function renderReview(message=""){
  const workflow=workflowOptions.find(item=>String(item.id)===String(selectedWorkflowId));
  const isAuto=workflow?.slug==="auto";
  const reviewCriteria=criteria.map(criterion=>`<section class="job-create-saved-criterion"><div class="job-create-saved-head"><strong>${escapeHtml(criterion.name)}</strong><span>${criterion.requirements.length} requirement${criterion.requirements.length===1?"":"s"}</span></div><ul>${criterion.requirements.map(requirement=>`<li>${escapeHtml(requirement.description)}${requirement.required?" · Required":""}</li>`).join("")}</ul></section>`).join("");
  renderFrame({stage:3,body:`
    <section class="job-create-panel">
      <h2>Review before publishing</h2><p>Check the job details, workflow, and saved criteria. Go back to edit any section.</p>
      <div class="job-create-review-grid">
        <div class="job-create-review-item"><small>Job title</small><strong>${escapeHtml(details.title)}</strong></div>
        <div class="job-create-review-item"><small>Location</small><strong>${escapeHtml(details.location)}</strong></div>
        <div class="job-create-review-item"><small>Salary</small><strong>${escapeHtml(details.salary)}</strong></div>
        <div class="job-create-review-item"><small>Deadline</small><strong>${escapeHtml(details.deadline)}</strong></div>
        <div class="job-create-review-item"><small>Workflow</small><strong>${escapeHtml(workflow?.slug==="auto"?"Fully Automated":"Semi Automated")}</strong></div>
        ${isAuto?`<div class="job-create-review-item"><small>AI threshold</small><strong>${escapeHtml(threshold)} / 100</strong></div>`:""}
        <div class="job-create-review-item full"><small>Description</small><strong class="job-create-review-description">${escapeHtml(details.description)}</strong></div>
      </div>
      <div class="job-create-review-criteria"><h3>Criteria and requirements</h3>${reviewCriteria}</div>
      <div class="job-create-error ${message?"show":""}" id="job-create-error" role="alert">${escapeHtml(message)}</div>
      <div class="job-create-actions"><button type="button" class="secondary" id="back-to-criteria">← Back to edit</button><button type="button" class="primary" id="publish-job">Publish job</button></div>
    </section>`});

  document.getElementById("back-to-criteria").addEventListener("click",()=>renderWorkflowAndCriteria());
  document.getElementById("publish-job").addEventListener("click",async event=>{
    const button=event.currentTarget;
    button.disabled=true;
    try{
      const result=await postAction({
        action:"publish_job",
        job_id:draftId,
        workflow_id:Number(selectedWorkflowId),
        screening_threshold:isAuto?Number(threshold):null,
        criteria:criteria.map(({name,requirements})=>({name,requirements:requirements.map(({description,required})=>({description,required}))})),
      });
      window.location.assign(result.redirect_url);
    }catch(error){showError(error.message);button.disabled=false;}
  });
}

if(manualWorkflow)selectedWorkflowId=manualWorkflow.id;
renderDetails();