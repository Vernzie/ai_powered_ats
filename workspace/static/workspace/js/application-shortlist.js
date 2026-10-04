(() => {
  const page = document.getElementById("shortlist-page");
  const dataElement = document.getElementById("shortlist-data");
  const form = document.getElementById("shortlist-form");
  if (!page || !dataElement || !form) return;

  const data = JSON.parse(dataElement.textContent);
  const applications = data.applications || [];
  const selectedId = Number(page.dataset.selectedApplicationId) || applications[0]?.id || null;
  const list = document.getElementById("shortlist-candidate-list");
  const review = document.getElementById("candidate-review-content");
  const heading = document.getElementById("candidate-review-heading");
  const overallScore = document.getElementById("candidate-overall-score");

  const escapeHtml = value => String(value ?? "").replace(/[&<>\"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[character]);

  function renderCandidateReview(application) {
    if (!application) {
      heading.textContent = "Select a candidate";
      overallScore.textContent = "—";
      review.innerHTML = '<p class="shortlist-empty">Select a candidate from the queue to review their scores and evidence.</p>';
      return;
    }

    heading.textContent = `${application.name} · ${application.email}`;
    overallScore.textContent = application.score == null ? "—" : `${application.score}%`;
    const groupedResults = new Map();
    (application.criteria_results || []).forEach(result => {
      const group = groupedResults.get(result.criterion) || [];
      group.push(result);
      groupedResults.set(result.criterion, group);
    });
    const criteriaMarkup = [...groupedResults.entries()].map(([criterion, results]) => `
      <section class="shortlist-criterion">
        <h3>${escapeHtml(criterion)}</h3>
        ${results.map(result => `
          <article class="shortlist-requirement">
            <div class="shortlist-requirement-heading">
              <strong>${escapeHtml(result.requirement)}${result.required?'<span class="shortlist-required-tag">Required</span>':""}</strong>
              <span class="shortlist-requirement-score">${result.score == null?"—":`${result.score}%`}</span>
            </div>
            <small>${escapeHtml(result.assessment)}${result.evidence?` · ${escapeHtml(result.evidence)}`:""}</small>
          </article>
        `).join("")}
      </section>
    `).join("");

    review.innerHTML = `
      <div class="shortlist-candidate-summary">
        <h3>${escapeHtml(application.name)}</h3>
        <p>${escapeHtml(application.email)}</p>
        ${application.reviewed_by?`<p class="shortlist-review-meta">Reviewed by ${escapeHtml(application.reviewed_by)}</p>`:""}
      </div>
      <div class="shortlist-ai-summary"><strong>Screening summary</strong><p>${escapeHtml(application.comments || "No overall screening comments saved.")}</p></div>
      ${criteriaMarkup || '<p class="shortlist-empty">No requirement-level scores are available for this application.</p>'}
    `;
  }

  list.addEventListener("click", event => {
    const reviewButton = event.target.closest("[data-view-application]");
    if (!reviewButton) return;
    const application = applications.find(item => item.id === Number(reviewButton.dataset.viewApplication));
    list.querySelectorAll(".shortlist-candidate").forEach(row => row.classList.toggle("is-current", row.dataset.applicationId === String(application?.id)));
    renderCandidateReview(application);
  });

  const selectedApplication = applications.find(application => application.id === selectedId) || applications[0] || null;
  if (selectedApplication) {
    const selectedRow = list.querySelector(`[data-application-id="${selectedApplication.id}"]`);
    selectedRow?.classList.add("is-current");
    renderCandidateReview(selectedApplication);
  }
})();
