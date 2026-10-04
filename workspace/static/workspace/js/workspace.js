const c=document.getElementById("pageContent"),workspaceData=JSON.parse(document.getElementById("workspace-data").textContent);
const escapeHtml=value=>String(value??"").replace(/[&<>\"']/g,character=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
const statusMeta={
  RECEIVED:{label:"Received",className:"submitted"},
  SCREENED:{label:"Screened",className:"screening"},
  SHORTLISTED:{label:"Shortlisted",className:"shortlisted"},
  INTERVIEWED:{label:"Interview Prep",tabLabel:"Interview Prep",className:"interviewed"},
  REJECTED:{label:"Rejected",className:"rejected"},
};
const csrfToken=document.cookie.split("; ").find((row)=>row.startsWith("csrftoken="))?.split("=")[1] || "";
const statusOrder = workspaceData.status_order || ["RECEIVED","SCREENED","SHORTLISTED","INTERVIEWED"];
let selectedJob = workspaceData.selected_job;
const workspaceQuery = new URLSearchParams(window.location.search);
const requestedApplicationId = Number(workspaceQuery.get("application")) || null;
const requestedApplication = selectedJob?.applications?.find(application=>application.id===requestedApplicationId);
const requestedStage = workspaceQuery.get("status") || requestedApplication?.status;
const defaultStatusFilter = statusOrder.includes(requestedStage) || statusMeta[requestedStage] ? requestedStage : "RECEIVED";
if (requestedApplication) window.__workspaceSelectedCandidateId = requestedApplication.id;
let settingsFeedback = "";
let settingsEditing = false;
let jobContextExpanded = true;
let selectedApplicationIds = new Set();
let receivedActionMode = "";
let bulkScreeningProgress = null;
let shortlistFilterMode = "";
let customShortlistThreshold = "";
let shortlistSubmitting = false;
let shortlistFeedback = "";
let interviewSubmitting = false;
let interviewFeedback = "";

function workflowClass(slug){
  const normalized=(slug||"").toLowerCase();
  if (normalized.includes("semi") || normalized.includes("manual")) return "semi";
  if (normalized.includes("auto")) return "auto";
  return "";
}

function applyStatus(text){
  const meta=statusMeta[text]||{label:text,className:"submitted"};
  return `<span class="review-status ${meta.className}">${meta.label}</span>`;
}

function renderEmpty(){
  const jobs = workspaceData.jobs || [];
  const jobOptionsMarkup = jobs.map(job=>
    `<option value="${job.id}">${escapeHtml(job.title)} · ${escapeHtml(job.location)}</option>`
  ).join("");
  c.innerHTML=`
    <style>
      .workspace-job-selector-container{margin:0 0 16px;padding:12px 14px;border:1px solid var(--line);background:#fff;}
      .workspace-job-picker label{display:grid;gap:5px;width:min(100%,620px);color:var(--muted);font-size:11px;font-weight:650;}
      .workspace-job-picker select{width:100%;height:42px;padding:0 12px;border:1px solid var(--line);background:#fff;color:var(--text);font-size:14px;font-weight:600;}
      .workspace-job-empty{min-height:120px;display:grid;place-items:center;color:var(--muted);font-size:13px;text-align:center;}
      @media(max-width:700px){.workspace-job-selector-container{padding:10px}.workspace-job-picker label{width:100%}}
    </style>
    <div class="workspace-job-selector-container">
      <div class="workspace-job-picker">
        <label for="workspace-job-select">Select a job
          <select id="workspace-job-select" ${jobs.length?"":"disabled"}>
            <option value="" selected disabled>${jobs.length?"Choose a job":"No active jobs available"}</option>
            ${jobOptionsMarkup}
          </select>
        </label>
      </div>
    </div>
    <div class="workspace-job-empty">${jobs.length?"Choose a job to view its applications.":"No active jobs to review."}</div>
  `;

  document.getElementById("workspace-job-select")?.addEventListener("change", event=>{
    const job = jobs.find(item=>String(item.id)===event.target.value);
    if (job?.url) window.location.assign(job.url);
  });
}

function render(){
  if (!selectedJob || !workspaceData.jobs?.length){ renderEmpty(); return; }

  const activeFilter = window.__workspaceActiveStage || defaultStatusFilter;
  const candidateList = selectedJob.applications || [];
  const workflowOptions = workspaceData.workflow_options || [];
  const isFullyAutomated = selectedJob.workflow_slug === "auto";
  const thresholdValue = selectedJob.screening_threshold ?? 70;
  const workflowOptionsMarkup = workflowOptions.map(workflow=>`<option value="${workflow.id}" data-slug="${escapeHtml(workflow.slug)}" ${String(workflow.id)===String(selectedJob.workflow_id)?"selected":""}>${workflow.slug==="auto"?"Fully Automated":"Semi Automated"}</option>`).join("");
  const stageCandidates = candidateList.filter(application=>application.status === activeFilter);
  const shortlistThreshold = activeFilter === "SCREENED" ? getShortlistFilterThreshold() : null;
  const hasShortlistThreshold = activeFilter === "SCREENED" && shortlistThreshold !== null;
  const visibleCandidates = hasShortlistThreshold
    ? stageCandidates.filter(application=>application.score != null && Number(application.score) > shortlistThreshold)
    : stageCandidates;
  const selectedCandidateId = window.__workspaceSelectedCandidateId || (visibleCandidates[0]?.id ?? null);
  const selectedCandidate = visibleCandidates.find((application)=>application.id === selectedCandidateId)
    || visibleCandidates[0]
    || null;
  if (selectedCandidate) window.__workspaceSelectedCandidateId = selectedCandidate.id;
  const selectedActionApplications = [...selectedApplicationIds]
    .map(applicationId=>candidateList.find(application=>application.id === applicationId))
    .filter(Boolean);
  const selectedActionApplication = selectedActionApplications.length === 1
    ? selectedActionApplications[0]
    : null;
  const canReviewSelected = Boolean(
    selectedActionApplication
    && selectedActionApplication.resume_available
    && ["RECEIVED","SCREENED","SHORTLISTED","REJECTED"].includes(selectedActionApplication.status)
  );
  const bulkScreenCandidates = receivedActionMode === "bulk-screen-ai"
    ? selectedActionApplications.filter(application=>
        application
        && application.resume_available
        && ["RECEIVED","SCREENED","SHORTLISTED","REJECTED"].includes(application.status)
      )
    : [];
  const canBulkScreenSelected = receivedActionMode === "bulk-screen-ai"
    && bulkScreenCandidates.length > 0;
  const isBulkScreening = bulkScreeningProgress !== null;
  const canShortlistFiltered = hasShortlistThreshold && visibleCandidates.length > 0 && !shortlistSubmitting;
  const showScreeningActionMenu = activeFilter === "RECEIVED";
  const showInterviewAction = activeFilter === "SHORTLISTED";
  const showInterviewStageAction = activeFilter === "INTERVIEWED";
  const interviewSelectionEnabled = showInterviewAction;
  const interviewPreparationSelectionEnabled = showInterviewStageAction;
  const canPrepareInterview = interviewPreparationSelectionEnabled
    && selectedActionApplications.length === 1
    && selectedActionApplications[0].status === "INTERVIEWED";
  const canAddToInterview = showInterviewAction
    && selectedActionApplications.length > 0
    && selectedActionApplications.every(application=>application.status === "SHORTLISTED")
    && !interviewSubmitting;
  const screeningActionMenuMarkup = showScreeningActionMenu ? `
    <div class="workspace-received-action-menu-wrap">
      <label class="workspace-received-action-label" for="workspace-received-action-menu">Action</label>
      <select id="workspace-received-action-menu" class="workspace-received-action-menu" aria-label="Choose a screening action" ${isBulkScreening?"disabled":""}>
        <option value="" ${receivedActionMode ? "" : "selected"}>Select action</option>
        <option value="bulk-screen-ai" ${receivedActionMode === "bulk-screen-ai" ? "selected" : ""}>Bulk Screen using AI</option>
        <option value="individual-screen" ${receivedActionMode === "individual-screen" ? "selected" : ""}>Individual Screen</option>
      </select>
    </div>
  ` : "";
  const showShortlistFilter = activeFilter === "SCREENED";
  const shortlistFilterMarkup = showShortlistFilter ? `
    <div class="workspace-received-action-menu-wrap">
      <label class="workspace-received-action-label" for="workspace-shortlist-filter">Filter</label>
      <select id="workspace-shortlist-filter" class="workspace-received-action-menu" aria-label="Filter screened applications by score" ${shortlistSubmitting?"disabled":""}>
        <option value="" ${shortlistFilterMode===""?"selected":""}>Select filter</option>
        <option value="over-90" ${shortlistFilterMode==="over-90"?"selected":""}>Over 90</option>
        <option value="over-95" ${shortlistFilterMode==="over-95"?"selected":""}>Over 95</option>
        <option value="custom" ${shortlistFilterMode==="custom"?"selected":""}>Custom</option>
      </select>
      ${shortlistFilterMode==="custom"?`<input class="workspace-shortlist-custom-input" id="workspace-shortlist-custom-threshold" type="number" min="0" max="100" step="1" value="${escapeHtml(customShortlistThreshold)}" aria-label="Custom minimum score" placeholder="Score" ${shortlistSubmitting?"disabled":""}>`:""}
    </div>
  ` : "";
  const screeningSelectionEnabled = showScreeningActionMenu && Boolean(receivedActionMode);

  const jobOptionsMarkup = workspaceData.jobs.map(job=>
    `<option value="${job.id}" ${String(job.id)===String(selectedJob.id)?"selected":""}>${escapeHtml(job.title)} · ${escapeHtml(job.location)}</option>`
  ).join("");

  const stageMarkup = statusOrder.map((status)=>{
    const count = selectedJob.counts?.[status] ?? 0;
    const meta = statusMeta[status] || { label: status, className: "submitted" };
    const isActive = activeFilter === status;
    return `
      <button type="button" class="workspace-stage-tab ${isActive ? "is-active" : ""}" role="tab" aria-selected="${isActive}" data-stage-filter="${status}" ${isBulkScreening?"disabled":""}>
        <span>${meta.tabLabel || meta.label}</span><strong>${count}</strong>
      </button>
    `;
  }).join("");

  const candidateMarkup = visibleCandidates.length ? visibleCandidates.map((application)=>{
    const score = application.score != null ? `${application.score}%` : "—";
    const canReview = ["RECEIVED","SCREENED","SHORTLISTED","REJECTED"].includes(application.status) && application.resume_available;
    const selectionCheckbox = interviewPreparationSelectionEnabled
      ? `<input class="workspace-application-selection" type="checkbox" value="${application.id}" aria-label="Select ${escapeHtml(application.name)} to prepare interview questions" ${selectedApplicationIds.has(application.id)?"checked":""}>`
      : interviewSelectionEnabled
      ? `<input class="workspace-application-selection" type="checkbox" value="${application.id}" aria-label="Select ${escapeHtml(application.name)} to add to interviews" ${selectedApplicationIds.has(application.id)?"checked":""} ${interviewSubmitting?"disabled":""}>`
      : screeningSelectionEnabled && receivedActionMode === "bulk-screen-ai" && canReview
        ? `<input class="workspace-application-selection" type="checkbox" value="${application.id}" aria-label="Select ${escapeHtml(application.name)} for screening" ${selectedApplicationIds.has(application.id)?"checked":""} ${canReview&&!isBulkScreening?"":"disabled"}>`
        : "";
    const singleApplicationArrow = receivedActionMode === "individual-screen" && application.status === "RECEIVED"
      ? `<button type="button" class="workspace-candidate-arrow" data-application-id="${application.id}" aria-label="Open ${escapeHtml(application.name)} for review">→</button>`
      : "";
    return `
      <div class="workspace-candidate ${selectedCandidate && selectedCandidate.id === application.id ? "selected" : ""}" data-candidate-id="${application.id}" role="button" tabindex="0" aria-pressed="${selectedCandidate && selectedCandidate.id === application.id}">
        ${selectionCheckbox}
        <div class="candidate-avatar">${escapeHtml(application.name).charAt(0).toUpperCase() || "A"}</div>
        <div class="candidate-content">
          <strong>${escapeHtml(application.name)}</strong>
          <small>${escapeHtml(application.email)}</small>
          <small>${escapeHtml(application.status_label)} · ${escapeHtml(application.applied_date)}</small>
          ${application.status === "INTERVIEWED" ? `<small>${application.interview_question_count ?? 0} question${application.interview_question_count === 1 ? "" : "s"}</small>` : ""}
          ${application.resume_available?"":'<small class="workspace-resume-missing">Resume file missing · re-upload to screen</small>'}
        </div>
        <div class="candidate-score">${score}</div>
        ${singleApplicationArrow}
      </div>
    `;
  }).join("") : `<div class="review-empty">No applications match this stage.</div>`;

  const selectedStatus = selectedCandidate ? selectedCandidate.status : "RECEIVED";
  const selectedStatusIndex = statusOrder.indexOf(selectedStatus);
  const scoreMarkup = selectedCandidate && selectedCandidate.score != null ? `<strong>${selectedCandidate.score}%</strong>` : `<strong>—</strong>`;
  const commentsMarkup = selectedCandidate && selectedCandidate.screening_comments ? `<div class="assessment-note"><strong>AI summary</strong><span>${escapeHtml(selectedCandidate.screening_comments)}</span></div>` : `<div class="assessment-note"><strong>AI summary</strong><span>No screening summary has been saved yet.</span></div>`;
  const criteriaMarkup = workspaceData.selected_job.criteria?.length ? workspaceData.selected_job.criteria.map(criterion=>{
    const requirements = criterion.requirements.map(requirement=>{
      const result = selectedCandidate?.criteria_results?.find(item=>item.requirement_id===requirement.id);
      const score = result?.score ?? null;
      const scoreClass = score===null ? "none" : score>=80 ? "high" : score>=60 ? "mid" : "low";
      const assessment = result ? escapeHtml(result.assessment) : "Not assessed";
      const evidence = result?.evidence ? ` · ${escapeHtml(result.evidence)}` : "";
      return `<div class="workspace-requirement"><div class="workspace-requirement-top"><span>${escapeHtml(requirement.name)}${requirement.required?'<em>Required</em>':""}</span><strong>${score===null?"—":`${score}%`}</strong></div><div class="workspace-scorebar"><i class="${scoreClass}" style="width:${score===null?0:Math.min(100,Math.max(0,score))}%"></i></div><small>${assessment}${evidence}</small></div>`;
    }).join("");
    return `<section class="workspace-criterion"><div class="workspace-criterion-heading"><h3>${escapeHtml(criterion.name)}</h3><span>${criterion.requirements.length} requirement${criterion.requirements.length===1?"":"s"}</span></div>${requirements||'<p class="review-empty">No requirements in this criterion.</p>'}</section>`;
  }).join("") : `<p class="workspace-criteria-empty">No criteria have been added to this job yet.</p>`;
  c.innerHTML = `
    <style>
      .workspace-shell{display:block;}
      .workspace-panel{background:#fff;border:1px solid var(--line);padding:18px;}
      .workspace-job-context{margin:0 0 16px;border:1px solid var(--line);background:#fff;}
      .workspace-job-context-toggle{width:100%;min-height:42px;display:flex;align-items:center;gap:12px;padding:9px 14px;border:0;background:#f8fafc;color:var(--text);cursor:pointer;text-align:left;font:inherit;}
      .workspace-job-context-label{color:var(--muted);font-size:10px;font-weight:700;white-space:nowrap;}
      .workspace-job-context-current{flex:1;min-width:0;font-size:12px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
      .workspace-job-context-action{color:var(--blue);font-size:10px;font-weight:700;white-space:nowrap;}
      .workspace-job-context-chevron{width:8px;height:8px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg);transition:transform .16s ease;}
      .workspace-job-context-toggle[aria-expanded="true"] .workspace-job-context-chevron{transform:rotate(225deg);}
      .workspace-job-context-content[hidden]{display:none;}
      .workspace-job-selector-container{margin:0 0 16px;padding:12px 14px;border:1px solid var(--line);background:#fff;}
      .workspace-job-picker{display:flex;align-items:center;gap:14px;}
      .workspace-job-picker label{display:grid;gap:5px;min-width:0;width:min(100%,620px);color:var(--muted);font-size:11px;font-weight:650;}
      .workspace-job-picker select{width:100%;height:42px;padding:0 12px;border:1px solid var(--line);background:#fff;color:var(--text);font-size:14px;font-weight:600;}
      .workspace-main{display:grid;gap:18px;}
      .workspace-header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;}
      .workspace-page-heading{align-items:flex-start;gap:18px;}
      .workspace-header-tools{display:grid;justify-items:end;gap:8px;min-width:min(100%,430px);}
      .workspace-job-settings{display:grid;grid-template-columns:minmax(130px,1fr) minmax(120px,.9fr) auto;align-items:end;gap:8px;width:100%;padding:10px;border:1px solid var(--line);background:#fff;}
      .workspace-job-settings label{display:grid;gap:4px;color:var(--muted);font-size:9px;font-weight:650;}
      .workspace-job-settings label[hidden]{display:none;}
      .workspace-job-settings select,.workspace-job-settings input{width:100%;min-width:0;height:34px;border:1px solid var(--line);background:#fff;padding:0 8px;color:var(--text);font-size:11px;}
      .workspace-job-settings select:disabled,.workspace-job-settings input:disabled{background:#f1f3f5;color:var(--muted);opacity:1;}
      .workspace-threshold-control{display:flex;align-items:center;gap:6px;}
      .workspace-threshold-control span{font-size:11px;color:var(--muted);}
      .workspace-job-settings button{height:34px;padding:0 11px;white-space:nowrap;font-size:10px;}
      .workspace-settings-feedback{grid-column:1/-1;min-height:12px;color:var(--muted);font-size:9px;}
      .workspace-settings-feedback.is-error{color:var(--red);}
      .workspace-header h1{margin:0;font-size:28px;letter-spacing:-.03em;} 
      .workspace-header p{color:var(--muted);margin:5px 0 0;}
      .workspace-heading-main{display:flex;align-items:flex-start;gap:12px;min-width:0;}
      .workspace-stage-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:1px solid var(--line);margin:0 0 16px;}
      .workspace-stage-tab{min-height:46px;border:0;border-bottom:2px solid transparent;background:#fff;color:var(--muted);padding:10px 12px;display:flex;align-items:center;justify-content:center;gap:9px;cursor:pointer;font:inherit;font-size:12px;font-weight:650;}
      .workspace-stage-tab strong{min-width:22px;height:22px;border-radius:11px;background:#f1f4f6;color:var(--text);display:grid;place-items:center;font-size:10px;}
      .workspace-stage-tab.is-active{color:var(--text);border-bottom-color:var(--blue);}
      .workspace-stage-tab.is-active strong{background:#e5edff;color:#24499a;}
      .workspace-candidate-area{display:grid;grid-template-columns:minmax(230px,28%) minmax(0,1fr);gap:18px;align-items:start;}
      .workspace-candidate-list{display:grid;gap:8px;margin-top:0;}
      .workspace-candidate{border:1px solid var(--line);padding:10px 12px;background:#fff;display:grid;grid-template-columns:18px 34px minmax(0,1fr) auto;gap:10px;align-items:center;cursor:pointer;text-align:left;width:100%;}
      .workspace-candidate.is-arriving{animation:workspace-candidate-arrive .32s ease-out both;}
      @keyframes workspace-candidate-arrive{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
      .workspace-candidate.selected{background:#eef3ff;border-color:#dfe8ff;}
      .workspace-application-selection{width:15px;height:15px;margin:0;accent-color:var(--blue);cursor:pointer;}
      .workspace-application-selection:disabled{cursor:not-allowed;}
      .workspace-screen-action{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:12px;}
      .workspace-screen-action-copy{display:grid;gap:3px;}
      .workspace-screen-action-copy strong{font-size:11px;color:var(--text);}
      .workspace-screen-action-copy small{font-size:9px;color:var(--muted);}
      .workspace-screen-action button{font-size:10px;padding:7px 11px;}
      .workspace-screen-action button:disabled{opacity:.45;cursor:not-allowed;}
      .workspace-screen-action .bulk-screen-button{height:34px;min-width:110px;display:inline-flex;align-items:center;justify-content:center;gap:8px;}
      .workspace-screen-spinner{width:13px;height:13px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:workspace-screen-spin .7s linear infinite;}
      @keyframes workspace-screen-spin{to{transform:rotate(360deg)}}
      .workspace-received-action-menu-wrap{display:flex;align-items:center;gap:10px;min-width:0;}
      .workspace-received-action-label{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);min-width:44px;white-space:nowrap;}
      .workspace-received-action-menu{height:34px;border:1px solid var(--line);background:#fff;padding:0 8px;color:var(--text);font-size:11px;min-width:180px;}
      .workspace-shortlist-custom-input{width:78px;height:34px;border:1px solid var(--line);background:#fff;padding:0 8px;color:var(--text);font-size:11px;}
      .workspace-shortlist-feedback{color:var(--red);font-size:10px;}
      .candidate-avatar{width:34px;height:34px;border-radius:50%;background:#dfe8ff;color:#26469c;display:grid;place-items:center;font-weight:700;}
      .candidate-content strong{display:block;font-size:14px;}
      .candidate-content small{display:block;color:var(--muted);font-size:11px;line-height:1.5;}
      .candidate-content .workspace-resume-missing{color:var(--red);font-weight:650;}
      .candidate-score{font-size:14px;font-weight:700;}
      .workspace-candidate-arrow{width:32px;height:32px;border:1px solid var(--line);background:#fff;color:var(--blue);border-radius:50%;display:grid;place-items:center;cursor:pointer;font-size:18px;line-height:1;padding:0;}
      .workspace-candidate-arrow:hover{background:#edf2ff;border-color:#cbd8ff;}
      .workspace-review-panel{display:grid;align-content:start;gap:14px;padding:18px;background:#f8fafc;border:1px solid var(--line);height:auto;max-height:none;min-height:0;overflow:visible;}
      .workspace-review-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;}
      .workspace-review-top h2{margin:0;font-size:22px;}
      .workspace-review-top p{margin:5px 0 0;color:var(--muted);font-size:13px;}
      .workspace-review-score{font-size:28px;font-weight:800;line-height:1;}
      .workspace-review-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
      .workspace-review-actions select{height:34px;border:1px solid var(--line);padding:0 8px;min-width:150px;}
      .workspace-stage-navigation{display:flex;justify-content:space-between;align-items:center;gap:14px;padding-top:12px;border-top:1px solid var(--line);}
      .workspace-stage-navigation button{width:38px;height:38px;border:1px solid var(--line);background:#fff;color:var(--blue);font-size:23px;line-height:1;}
      .workspace-stage-navigation button:hover:not(:disabled){background:#edf2ff;border-color:#cbd8ff;}
      .workspace-stage-navigation button:disabled{opacity:.35;cursor:not-allowed;}
      .workspace-stage-current{text-align:center;}
      .workspace-stage-current small{display:block;color:var(--muted);font-size:9px;}
      .workspace-stage-current strong{font-size:11px;}
      .assessment-note{padding:12px;border-left:3px solid var(--blue);background:#f8fafd;}
      .assessment-note strong{display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}
      .assessment-note span{font-size:13px;line-height:1.6;color:#3a434d;}
      .workspace-criteria{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:18px;padding:4px 6px 4px 0;}
      .workspace-criteria-box{border:1px solid var(--line);background:#fff;padding:16px;}
      .workspace-criteria-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;}
      .workspace-criteria-heading h3{margin:0;font-size:15px;}
      .workspace-criteria-heading span,.workspace-criterion-heading span{font-size:11px;color:var(--muted);}
      .workspace-criterion{border-top:1px solid var(--line);padding-top:12px;}
      .workspace-criterion-heading{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:6px;}
      .workspace-criterion-heading h3{margin:0;font-size:14px;}
      .workspace-requirement{padding:12px 13px;margin:9px 0;border:1px solid #dfe5ec;border-radius:4px;background:#f8fafc;box-shadow:0 1px 3px rgba(23,35,52,.08);}
      .workspace-requirement-top{display:flex;justify-content:space-between;gap:10px;align-items:center;}
      .workspace-requirement-top span{font-size:13px;line-height:1.45;}
      .workspace-requirement-top strong{min-width:48px;padding:4px 7px;border:1px solid #d7e3ff;border-radius:4px;background:#eaf1ff;color:#244f9b;font-size:13px;font-weight:750;text-align:center;white-space:nowrap;}
      .workspace-requirement-top em{font-size:10px;color:var(--red);font-style:normal;margin-left:5px;}
      .workspace-scorebar{height:7px;background:#e1e7ef;margin:9px 0 6px;border-radius:4px;overflow:hidden;}
      .workspace-scorebar i{display:block;height:100%;background:#cbd0d6;transition:width .5s ease;}
      .workspace-scorebar i.high{background:var(--green);}
      .workspace-scorebar i.mid{background:#bd8420;}
      .workspace-scorebar i.low{background:var(--red);}
      .workspace-requirement small{display:block;color:var(--muted);font-size:12px;line-height:1.55;overflow-wrap:anywhere;}
      .workspace-criteria-empty{margin:0;color:var(--muted);font-size:13px;}
      .workspace-move-row{display:flex;flex-wrap:wrap;gap:8px;}
      .workspace-empty{min-height:240px;display:grid;align-content:center;justify-items:center;text-align:center;color:var(--muted);}
      .workspace-empty strong{color:var(--text);font-size:17px;}
      .workspace-empty p{margin:6px 0 0;font-size:12px;}
      @media(max-width:1200px){.workspace-candidate-area{grid-template-columns:1fr}.workspace-header-tools{min-width:380px}}
      @media(max-width:800px){.workspace-page-heading{flex-wrap:wrap}.workspace-header-tools{width:100%;min-width:0;justify-items:stretch}}
      @media(max-width:700px){.workspace-job-selector-container{padding:10px}.workspace-job-picker label{width:100%}.workspace-panel{padding:16px}.workspace-stage-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}.workspace-stage-tab{justify-content:space-between}.workspace-review-panel{max-height:none;overflow:visible;border-top:1px solid var(--line);padding-top:14px}.workspace-criteria{grid-template-columns:1fr}}
    </style>
    <section class="workspace-job-context">
      <button type="button" class="workspace-job-context-toggle" id="workspace-job-context-toggle" aria-expanded="${jobContextExpanded}" aria-controls="workspace-job-context-content" aria-label="${jobContextExpanded?"Hide":"Show"} job details">
        <span class="workspace-job-context-label">Job context</span>
        <span class="workspace-job-context-current">${jobContextExpanded?"Job details":`${escapeHtml(selectedJob.title)} · ${escapeHtml(selectedJob.workflow)} · ${escapeHtml(selectedJob.location)}`}</span>
        <span class="workspace-job-context-action">${jobContextExpanded?"Hide details":"Show details"}</span>
        <span class="workspace-job-context-chevron" aria-hidden="true"></span>
      </button>
      <div class="workspace-job-context-content" id="workspace-job-context-content" ${jobContextExpanded?"":"hidden"}>
        <div class="workspace-job-selector-container">
          <div class="workspace-job-picker">
            <label for="workspace-job-select">Select a job
              <select id="workspace-job-select">${jobOptionsMarkup}</select>
            </label>
          </div>
        </div>
        <div class="heading workspace-page-heading">
          <div class="workspace-heading-main">
            <div>
            <p class="eyebrow">JOB REVIEW WORKSPACE</p>
            <h1>${escapeHtml(selectedJob.title)}</h1>
            <p class="muted">${escapeHtml(selectedJob.workflow)} · ${escapeHtml(selectedJob.location)}</p>
            </div>
          </div>
          <div class="workspace-header-tools">
            <form class="workspace-job-settings" id="workspace-job-settings">
              <label>Workflow<select id="workspace-workflow-select" ${settingsEditing?"":"disabled"}><option value="" ${selectedJob.workflow_id?"":"selected"}>Choose workflow</option>${workflowOptionsMarkup}</select></label>
              <label class="workspace-threshold-field" ${isFullyAutomated?"":"hidden"}>AI threshold<div class="workspace-threshold-control"><input id="workspace-screening-threshold" type="number" min="0" max="100" step="1" value="${isFullyAutomated?thresholdValue:""}" ${settingsEditing&&isFullyAutomated?"required":""} ${settingsEditing&&isFullyAutomated?"":"disabled"}><span>%</span></div></label>
              <button class="secondary" type="submit">${settingsEditing?"Save":"Edit"}</button>
              <span class="workspace-settings-feedback ${settingsFeedback.startsWith("Could not")?"is-error":""}" id="workspace-settings-feedback" aria-live="polite">${escapeHtml(settingsFeedback|| (isFullyAutomated?"Applied to automatic shortlisting.":"Threshold disabled for semi-automated workflow."))}</span>
            </form>
          </div>
        </div>
      </div>
    </section>
    <div class="workspace-shell">
      <main class="workspace-main">
        <section class="workspace-panel">
          <div class="workspace-stage-tabs" role="tablist" aria-label="Application stages">${stageMarkup}</div>
          <div class="panelhead" style="padding:0 0 12px;border-bottom:1px solid var(--line);margin:0 0 12px;">
            <div>
                <h2 style="margin:0;font-size:14px;">${statusMeta[activeFilter]?.tabLabel || statusMeta[activeFilter]?.label} applications</h2>
              <p style="margin:3px 0 0;color:var(--muted);font-size:10px;">${visibleCandidates.length} application${visibleCandidates.length === 1 ? "" : "s"}</p>
            </div>
            <div class="workspace-screen-action">
              ${showShortlistFilter ? shortlistFilterMarkup : showInterviewAction ? `<div class="workspace-screen-action-copy"><strong>Actions</strong><small>${selectedApplicationIds.size} selected</small></div>` : showScreeningActionMenu ? screeningActionMenuMarkup : showInterviewStageAction ? `<div class="workspace-screen-action-copy"><strong>Actions</strong></div>` : `<div class="workspace-screen-action-copy"><strong>Actions</strong><small>${selectedApplicationIds.size} selected</small></div>`}
              ${showInterviewStageAction ? `<button type="button" class="primary bulk-screen-button" id="workspace-prepare-interview" ${canPrepareInterview?"":"disabled"}>Prepare questions</button>` : ""}
              ${showInterviewAction ? `
                <button type="button" class="primary bulk-screen-button" id="workspace-add-to-interview" ${canAddToInterview?"":"disabled"} ${interviewSubmitting?"disabled":""} aria-busy="${interviewSubmitting}">${interviewSubmitting?`<span class="workspace-screen-spinner" aria-hidden="true"></span><span>Adding…</span>`:"Add to interviews"}</button>
                ${interviewFeedback?`<span class="workspace-shortlist-feedback" role="status">${escapeHtml(interviewFeedback)}</span>`:""}
              ` : showShortlistFilter ? `
                <button type="button" class="primary bulk-screen-button" id="workspace-shortlist-filtered" ${canShortlistFiltered?"":"disabled"} ${shortlistSubmitting?"disabled":""} aria-busy="${shortlistSubmitting}">${shortlistSubmitting?`<span class="workspace-screen-spinner" aria-hidden="true"></span><span>Shortlisting…</span>`:"Shortlist"}</button>
                ${shortlistFeedback?`<span class="workspace-shortlist-feedback" role="status">${escapeHtml(shortlistFeedback)}</span>`:""}
              ` : showScreeningActionMenu && receivedActionMode === "bulk-screen-ai" ? `
                <button type="button" class="primary bulk-screen-button" id="workspace-review-selected" ${isBulkScreening||canBulkScreenSelected?"":"disabled"} ${isBulkScreening?"disabled":""} aria-busy="${isBulkScreening}" aria-live="polite">${isBulkScreening?`<span class="workspace-screen-spinner" aria-hidden="true"></span><span>Screening ${bulkScreeningProgress.completed}/${bulkScreeningProgress.total}</span>`:"Screen"}</button>
              ` : ""}
            </div>
          </div>
          <div class="workspace-candidate-area">
            <div class="workspace-candidate-list">${candidateMarkup}</div>
            <aside class="workspace-review-panel">
              ${selectedCandidate ? `
            <div class="workspace-review-top">
              <div>
                <p class="eyebrow">Candidate review</p>
                <h2>${escapeHtml(selectedCandidate.name)}</h2>
                <p>${escapeHtml(selectedCandidate.email)}</p>
              </div>
              <div class="workspace-review-score">${scoreMarkup}</div>
            </div>
            <div class="workspace-review-actions">
              <label class="count-pill" style="display:inline-block;">${applyStatus(selectedCandidate.status)}</label>
            </div>
            ${selectedCandidate.reviewed_by_label?`<p class="workspace-review-attribution">Reviewed by <strong>${escapeHtml(selectedCandidate.reviewed_by_label)}</strong></p>`:""}
            ${commentsMarkup}
            <section class="workspace-criteria-box">
              <div class="workspace-criteria-heading"><h3>AI criteria assessment</h3><span>${selectedCandidate?.criteria_results?.length||0} scored</span></div>
              <div class="workspace-criteria">${criteriaMarkup}</div>
              <div class="workspace-stage-navigation">
                <button type="button" id="workspace-previous-stage" aria-label="Move to previous stage" title="Move to previous stage" ${!selectedCandidate || selectedStatusIndex<=0?"disabled":""}>←</button>
                <div class="workspace-stage-current"><small>Current stage</small><strong>${statusMeta[selectedStatus]?.label || selectedStatus}</strong></div>
                <button type="button" id="workspace-next-stage" aria-label="Move to next stage" title="Move to next stage" ${!selectedCandidate || selectedStatusIndex<0 || selectedStatusIndex>=statusOrder.length-1?"disabled":""}>→</button>
              </div>
            </section>
              ` : `<div class="review-empty">Select an application to review.</div>`}
            </aside>
          </div>
        </section>
      </main>
    </div>
  `;

  document.getElementById("workspace-job-context-toggle")?.addEventListener("click", ()=>{
    jobContextExpanded = !jobContextExpanded;
    render();
    document.getElementById("workspace-job-context-toggle")?.focus();
  });

  document.getElementById("workspace-workflow-select")?.addEventListener("change", event=>{
    const fullyAutomated=event.target.selectedOptions[0]?.dataset.slug==="auto";
    const thresholdInput=document.getElementById("workspace-screening-threshold");
    const thresholdField=document.querySelector(".workspace-threshold-field");
    if (!thresholdInput) return;
    if (thresholdField) thresholdField.hidden=!fullyAutomated;
    thresholdInput.disabled=!settingsEditing||!fullyAutomated;
    thresholdInput.required=settingsEditing&&fullyAutomated;
    thresholdInput.value=fullyAutomated?(selectedJob.screening_threshold??70):"";
    settingsFeedback=fullyAutomated?"Set the minimum AI score for automatic shortlisting.":"Threshold disabled for semi-automated workflow.";
    const feedback=document.getElementById("workspace-settings-feedback");
    if (feedback){feedback.textContent=settingsFeedback;feedback.classList.remove("is-error");}
  });

  document.getElementById("workspace-job-settings")?.addEventListener("submit", async event=>{
    event.preventDefault();
    if (!settingsEditing){
      settingsEditing=true;
      settingsFeedback="";
      render();
      return;
    }
    const form=event.currentTarget;
    const workflowSelect=document.getElementById("workspace-workflow-select");
    const thresholdInput=document.getElementById("workspace-screening-threshold");
    const saveButton=form.querySelector('button[type="submit"]');
    const selectedWorkflow=workflowSelect?.selectedOptions[0];
    if (!selectedWorkflow?.value){
      settingsFeedback="Could not save: choose a workflow.";
      render();
      return;
    }
    saveButton.disabled=true;
    try {
      const response=await fetch(workspaceData.move_status_url,{
        method:"POST",
        headers:{"Content-Type":"application/json","X-CSRFToken":csrfToken},
        body:JSON.stringify({
          action:"save_job_settings",
          job_id:selectedJob.id,
          workflow_id:Number(selectedWorkflow.value),
          screening_threshold:selectedWorkflow.dataset.slug==="auto"?Number(thresholdInput.value):null,
        }),
      });
      const result=await response.json().catch(()=>({}));
      if (!response.ok) throw new Error(result.error||"The job settings could not be saved.");
      selectedJob.workflow=result.workflow;
      selectedJob.workflow_slug=result.workflow_slug;
      selectedJob.workflow_id=result.workflow_id;
      selectedJob.screening_threshold=result.screening_threshold;
      workspaceData.selected_job=selectedJob;
      const jobRow=workspaceData.jobs.find(job=>job.id===selectedJob.id);
      if (jobRow){jobRow.workflow=result.workflow;jobRow.workflow_slug=result.workflow_slug;}
      settingsEditing=false;
      settingsFeedback="Settings saved.";
      render();
    } catch(error) {
      settingsFeedback=`Could not save: ${error.message}`;
      const feedback=document.getElementById("workspace-settings-feedback");
      if(feedback){feedback.textContent=settingsFeedback;feedback.classList.add("is-error");}
    } finally {
      saveButton.disabled=false;
    }
  });

  document.getElementById("workspace-job-select")?.addEventListener("change", async event=>{
      const jobRow = workspaceData.jobs.find(job=>String(job.id)===event.target.value);
      const jobUrl = jobRow?.url;
      if (!jobUrl || String(selectedJob?.id) === String(jobRow.id)) return;
      event.target.disabled = true;
      try {
        const response = await fetch(`${jobUrl}?format=json`, {headers:{"Accept":"application/json"}});
        if (!response.ok) throw new Error("The selected job could not be loaded.");
        const data = await response.json();
        selectedJob = data.selected_job;
        workspaceData.selected_job = selectedJob;
        settingsEditing = false;
        window.__workspaceSelectedCandidateId = null;
        window.__workspaceActiveStage = "RECEIVED";
        selectedApplicationIds.clear();
        window.history.replaceState({}, "", jobUrl);
        render();
      } catch (error) {
        event.target.value = String(selectedJob.id);
        alert(error.message || "The selected job could not be loaded.");
      } finally {
        event.target.disabled = false;
      }
  });

  document.getElementById("workspace-received-action-menu")?.addEventListener("change", (event)=>{
    receivedActionMode = event.target.value || "";
    selectedApplicationIds.clear();
    render();
  });

  document.getElementById("workspace-shortlist-filter")?.addEventListener("change", event=>{
    shortlistFilterMode = event.target.value || "";
    shortlistFeedback = "";
    selectedApplicationIds.clear();
    render();
    if (shortlistFilterMode === "custom") {
      document.getElementById("workspace-shortlist-custom-threshold")?.focus();
    }
  });

  document.getElementById("workspace-shortlist-custom-threshold")?.addEventListener("input", event=>{
    customShortlistThreshold = event.target.value;
    shortlistFeedback = "";
    render();
    document.getElementById("workspace-shortlist-custom-threshold")?.focus();
  });

  document.querySelectorAll(".workspace-stage-tab").forEach((button)=>{
    button.addEventListener("click", ()=>{
      window.__workspaceActiveStage = button.dataset.stageFilter;
      selectedApplicationIds.clear();
      if (!["RECEIVED","SCREENED","SHORTLISTED"].includes(button.dataset.stageFilter)) {
        receivedActionMode = "";
      }
      render();
    });
  });

  document.querySelectorAll(".workspace-candidate").forEach((button)=>{
    button.addEventListener("click", (event)=>{
      if (event.target.closest(".workspace-candidate-arrow")) return;
      window.__workspaceSelectedCandidateId = Number(button.dataset.candidateId);
      render();
    });
    button.addEventListener("keydown",event=>{
      if(event.target!==button)return;
      if(event.key==="Enter"||event.key===" "){
        event.preventDefault();
        window.__workspaceSelectedCandidateId=Number(button.dataset.candidateId);
        render();
      }
    });
  });

  document.querySelectorAll(".workspace-candidate-arrow").forEach((button)=>{
    button.addEventListener("click", (event)=>{
      event.preventDefault();
      event.stopPropagation();
      const applicationId = Number(button.dataset.applicationId);
      const reviewUrl = selectedJob?.application_review_url;
      if (!reviewUrl) return;
      window.location.assign(`${reviewUrl}?application=${applicationId}`);
    });
  });

  document.querySelectorAll(".workspace-application-selection").forEach(checkbox=>{
    checkbox.addEventListener("click",event=>event.stopPropagation());
    checkbox.addEventListener("change",()=>{
      const applicationId=Number(checkbox.value);
      if (interviewPreparationSelectionEnabled) {
        selectedApplicationIds.clear();
        if (checkbox.checked) selectedApplicationIds.add(applicationId);
        render();
        return;
      }
      if (interviewSelectionEnabled) {
        if (checkbox.checked) selectedApplicationIds.add(applicationId);
        else selectedApplicationIds.delete(applicationId);
        render();
        return;
      }
      if(!screeningSelectionEnabled) return;
      if(checkbox.checked){
        if (receivedActionMode === "individual-screen") {
          selectedApplicationIds.clear();
          selectedApplicationIds.add(applicationId);
        } else {
          selectedApplicationIds.add(applicationId);
        }
      }
      else {
        selectedApplicationIds.delete(applicationId);
      }
      render();
    });
  });

  document.getElementById("workspace-review-selected")?.addEventListener("click", async ()=>{
    if (receivedActionMode === "bulk-screen-ai") {
      await screenSelectedApplications();
      return;
    }
    openSelectedApplicationReview(selectedActionApplication,canReviewSelected,selectedJob.application_review_url);
  });
  document.getElementById("workspace-shortlist-filtered")?.addEventListener("click",()=>{
    shortlistFilteredApplications(visibleCandidates,shortlistThreshold);
  });
  document.getElementById("workspace-add-to-interview")?.addEventListener("click",()=>{
    addSelectedApplicationsToInterview(selectedActionApplications);
  });
  document.getElementById("workspace-prepare-interview")?.addEventListener("click",()=>{
    if (!canPrepareInterview || !selectedActionApplication || !selectedJob.interview_preparation_url_template) return;
    const url = selectedJob.interview_preparation_url_template.replace(/\/0\/prepare\/$/, `/${selectedActionApplication.id}/prepare/`);
    window.location.assign(url);
  });

  const moveSelectedCandidate = async direction=>{
    if (!selectedCandidate || selectedStatusIndex<0) return;
    const nextStatus = statusOrder[selectedStatusIndex+direction];
    if (!nextStatus) return;
    const moveButtons = [document.getElementById("workspace-previous-stage"),document.getElementById("workspace-next-stage")];
    moveButtons.forEach(button=>{if(button)button.disabled=true;});
    try {
      await updateApplicationStatus(selectedCandidate.id,nextStatus);
      selectedJob.counts[selectedCandidate.status]=Math.max(0,(selectedJob.counts[selectedCandidate.status]||0)-1);
      selectedJob.counts[nextStatus]=(selectedJob.counts[nextStatus]||0)+1;
      selectedCandidate.status=nextStatus;
      selectedCandidate.status_label=workspaceData.status_labels[nextStatus]||statusMeta[nextStatus]?.label||nextStatus;
      window.__workspaceActiveStage=nextStatus;
      window.__workspaceSelectedCandidateId=selectedCandidate.id;
      render();
    } catch(error) {
      alert(error.message||"The application could not be moved to the adjacent stage.");
      moveButtons.forEach(button=>{if(button)button.disabled=false;});
    }
  };
  document.getElementById("workspace-previous-stage")?.addEventListener("click",()=>moveSelectedCandidate(-1));
  document.getElementById("workspace-next-stage")?.addEventListener("click",()=>moveSelectedCandidate(1));

}

function openSelectedApplicationReview(application,canReview,reviewUrl){
  if(!canReview||!application||!reviewUrl)return;
  window.location.assign(`${reviewUrl}?application=${application.id}`);
}

function getShortlistFilterThreshold(){
  if(shortlistFilterMode==="over-90")return 90;
  if(shortlistFilterMode==="over-95")return 95;
  if(shortlistFilterMode!=="custom"||customShortlistThreshold==="")return null;
  const threshold=Number(customShortlistThreshold);
  return Number.isFinite(threshold)&&threshold>=0&&threshold<=100?threshold:null;
}

async function addSelectedApplicationsToInterview(applications){
  if(!applications.length||interviewSubmitting||!selectedJob.application_interview_url)return;
  interviewSubmitting=true;
  interviewFeedback="";
  render();
  const payload=new URLSearchParams();
  applications.forEach(application=>payload.append("application_ids",String(application.id)));
  try {
    const response=await fetch(selectedJob.application_interview_url,{
      method:"POST",
      headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8","X-CSRFToken":csrfToken,"Accept":"application/json"},
      body:payload.toString(),
    });
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(result.error||"The selected applications could not be moved to interviews.");
    if(result.redirect_url){window.location.assign(result.redirect_url);return;}
    throw new Error("The interview request did not return a destination.");
  } catch(error) {
    interviewSubmitting=false;
    interviewFeedback=error.message||"The selected applications could not be moved to interviews.";
    render();
  }
}

async function shortlistFilteredApplications(applications,threshold){
  if(threshold===null||threshold===undefined||!applications.length||shortlistSubmitting)return;
  shortlistSubmitting=true;
  shortlistFeedback="";
  render();
  const payload=new URLSearchParams();
  applications.forEach(application=>payload.append("application_ids",String(application.id)));
  try {
    const response=await fetch(selectedJob.application_shortlist_url,{
      method:"POST",
      headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8","X-CSRFToken":csrfToken,"Accept":"application/json"},
      body:payload.toString(),
    });
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(result.error||"The filtered applications could not be shortlisted.");
    if(result.redirect_url){window.location.assign(result.redirect_url);return;}
    throw new Error("The shortlist request did not return a destination.");
  } catch(error) {
    shortlistSubmitting=false;
    shortlistFeedback=error.message||"The filtered applications could not be shortlisted.";
    render();
  }
}

async function screenSelectedApplications(){
  const applicationIds = [...selectedApplicationIds];
  if (!applicationIds.length) return;

  const screenableIds = applicationIds.filter((applicationId)=>{
    const application = selectedJob.applications.find((item)=>item.id === applicationId);
    return Boolean(application && application.resume_available && ["RECEIVED","SCREENED","SHORTLISTED","REJECTED"].includes(application.status));
  });

  if (!screenableIds.length) return;

  const failures = [];
  const successfulIds = [];
  bulkScreeningProgress = {completed: 0, total: screenableIds.length};
  render();
  for (const applicationId of screenableIds) {
    const application = selectedJob.applications.find((item)=>item.id === applicationId);
    if (!application) continue;

    try {
      const screenUrl = workspaceData.screen_application_url_template.replace(/\/0\/screen\/$/, `/${applicationId}/screen/`);
      const response = await fetch(screenUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, "Accept": "application/json" },
        body: "{}",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(result.error || `Screening failed for ${application.name}.`);
      }
      if (result.status !== "SCREENED") {
        throw new Error(`Screening did not move ${application.name} to the Screened stage.`);
      }

      const previousStatus = application.status;
      if (selectedJob.counts && selectedJob.counts[previousStatus] != null) {
        selectedJob.counts[previousStatus] = Math.max(0, (selectedJob.counts[previousStatus] || 0) - 1);
      }
      if (result.status) {
        selectedJob.counts[result.status] = (selectedJob.counts[result.status] || 0) + 1;
      }

      application.status = result.status || application.status;
      application.status_label = result.status_label || application.status_label;
      application.score = result.score ?? application.score;
      application.screening_comments = result.screening_comments ?? application.screening_comments;
      application.criteria_results = result.criteria_results ?? application.criteria_results ?? [];
      selectedApplicationIds.delete(applicationId);
      successfulIds.push(applicationId);
    } catch (error) {
      failures.push(`${application.name}: ${error.message}`);
    }
    bulkScreeningProgress.completed += 1;
    render();
  }

  bulkScreeningProgress = null;
  if (successfulIds.length) {
    selectedApplicationIds.clear();
    receivedActionMode = "";
    window.__workspaceActiveStage = "SCREENED";
    window.__workspaceSelectedCandidateId = successfulIds[successfulIds.length - 1];
  }
  render();
  if (failures.length) {
    alert(failures.join("\n"));
  }
}

async function updateApplicationStatus(applicationId, status){
  const response = await fetch(workspaceData.move_status_url, {
    method:"POST",
    headers:{"Content-Type":"application/json","X-CSRFToken":csrfToken},
    body: JSON.stringify({action:"move_application_status", application_id: applicationId, status})
  });
  if (!response.ok) {
    const data = await response.json().catch(()=>({}));
    throw new Error(data.error || "The application status could not be updated.");
  }
}

render();
