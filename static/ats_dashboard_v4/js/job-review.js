(function () {
    const jobData = JSON.parse(document.getElementById("job-data").textContent);
    const criteria = jobData.criteria || [];
    const applications = jobData.applications || [];
    let selectedApplicationId = applications[0]?.id ?? null;
    let selectedStatus = "all";
    let candidateListHidden = false;

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "\"": "&quot;",
            "'": "&#39;"
        })[character]);
    }

    function statusClass(status) {
        return {
            RECEIVED: "submitted",
            SCREENED: "screening",
            SHORTLISTED: "shortlisted",
            REJECTED: "rejected"
        }[status] || "submitted";
    }

    function resultClass(result) {
        return result === "Passed" ? "positive" : result === "Failed" ? "fail" : "";
    }

    function assessmentPanel(application) {
        if (!application) {
            return `<aside class="assessment-panel"><div class="review-empty"><h3>Select a candidate</h3><p>Choose a candidate from the list.</p></div></aside>`;
        }

        const evidence = criteria.map(criterion => {
            const requirements = criterion.requirements.map(requirement => {
                const result = application.criteriaResults.find(item => item.requirementId === requirement.id);
                const score = result?.score ?? null;
                const scoreClass = score === null ? "none" : score >= 80 ? "high" : score >= 60 ? "mid" : "low";
                const assessment = result ? escapeHtml(result.assessment) : "Not assessed";
                const evidenceText = result ? escapeHtml(result.evidence) : "No screening evidence available.";
                return `<div class="requirement"><div class="req-top"><span>${escapeHtml(requirement.name)}${requirement.required ? " <em>Required</em>" : ""}</span><b>${score === null ? "—" : `${score}%`}</b></div><div class="scorebar"><i class="${scoreClass}" style="width:${score === null ? 0 : Math.min(100, Math.max(0, score))}%"></i></div><small>${assessment} · ${evidenceText}</small></div>`;
            }).join("");
            return `<div class="criteria-section"><div class="criteria-section-head"><div><h3>${escapeHtml(criterion.name)}</h3><small>${criterion.requirements.length} requirements</small></div></div><div class="requirement-grid">${requirements || `<p class="live-review-empty">No requirements in this criterion.</p>`}</div></div>`;
        }).join("");

        return `<aside class="assessment-panel"><div class="candidate-review"><div class="review-top"><div><p class="eyebrow">CANDIDATE ASSESSMENT</p><h2>${escapeHtml(application.name)}</h2><p>${escapeHtml(application.email)} · <a class="textbtn" href="${application.detailUrl}">Open full application →</a></p><div class="live-assessment-meta">${escapeHtml(application.statusLabel)} · ${escapeHtml(application.result)}</div></div><div class="review-score"><small>Overall score</small><strong>${application.score === null ? "—" : `${application.score}%`}</strong></div></div><div class="assessment-note"><strong>${escapeHtml(application.result)}</strong><span>${application.score === null ? "This application has not been screened." : "Screening data is shown for the selected candidate."}</span></div>${evidence || `<div class="live-review-empty">No criteria are available to assess.</div>`}</div></aside>`;
    }

    function renderReview() {
        const visibleApplications = applications.filter(application => selectedStatus === "all" || application.status === selectedStatus);
        if (!visibleApplications.some(application => application.id === selectedApplicationId)) {
            selectedApplicationId = visibleApplications[0]?.id ?? null;
        }
        const selectedApplication = visibleApplications.find(application => application.id === selectedApplicationId) || null;
        const statuses = [...new Map(applications.map(application => [application.status, application.statusLabel])).entries()];
        const candidateRows = visibleApplications.map(application => `<div class="candidate-row ${application.id === selectedApplicationId ? "selected" : ""}" aria-current="${application.id === selectedApplicationId}"><div class="candidate-info"><a class="candidate-name-link" href="${escapeHtml(application.detailUrl)}">${escapeHtml(application.name)}</a><small>${escapeHtml(application.email)}</small></div><span class="review-status ${statusClass(application.status)}">${escapeHtml(application.statusLabel)}</span><div class="candidate-score">${application.score === null ? "—" : `${application.score}%`}</div></div>`).join("");
        const statusOptions = statuses.map(([value, label]) => `<option value="${value}" ${selectedStatus === value ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");

        document.getElementById("jobBody").innerHTML = `<div class="review-toolbar"><div><strong>Application review workstation</strong><small>Review candidates against this job's criteria.</small></div><div class="review-toolbar-actions"><span class="count-pill">${visibleApplications.length} applications</span><select id="live-status-filter"><option value="all">All statuses</option>${statusOptions}</select><button class="secondary" id="toggle-candidate-list" type="button" aria-expanded="${!candidateListHidden}">${candidateListHidden ? "Show candidate list" : "Hide candidate list"}</button></div></div><div class="review-layout ${candidateListHidden ? "candidate-list-collapsed" : ""}"><section class="candidate-panel"><div class="candidate-panel-head"><div><h3>Candidates</h3><small>${visibleApplications.length} applications for this job</small></div><div class="legend">Candidate status · AI score</div></div>${candidateRows || `<div class="review-empty">No applications for this job.</div>`}</section>${assessmentPanel(selectedApplication)}</div>`;

        document.getElementById("live-status-filter").addEventListener("change", event => {
            selectedStatus = event.target.value;
            renderReview();
        });
        document.getElementById("toggle-candidate-list").addEventListener("click", () => {
            candidateListHidden = !candidateListHidden;
            renderReview();
        });
    }

    window.renderReview = renderReview;
})();