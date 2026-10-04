(() => {
  const form = document.getElementById("application-review-form");
  if (!form) return;

  const rows = [...form.querySelectorAll("[data-requirement-id]")];
  const submitButton = document.getElementById("send-to-screened");
  const aiButton = document.getElementById("run-ai-review");
  const aiButtonLabel = aiButton?.querySelector(".ai-review-button-label");
  const backLink = document.getElementById("application-review-back-link");
  const reviewMethod = document.getElementById("review-method");
  const fileIdInput = document.getElementById("review-file-id");
  const commentsInput = form.querySelector('[name="overall_comments"]');
  const feedback = document.getElementById("review-feedback");
  const overallScoreDisplay = document.getElementById("review-overall-score");
  const overallScoreValue = document.getElementById("review-overall-score-value");
  const resumeAvailable = form.dataset.resumeAvailable === "true";
  const csrfToken = document.cookie.split("; ").find(row => row.startsWith("csrftoken="))?.split("=")[1] || "";

  function updateSubmitState() {
    const allComplete = rows.length > 0 && rows.every(row => {
      const score = row.querySelector(".requirement-score").value;
      const assessment = row.querySelector(".requirement-assessment").value;
      return score !== "" && Number.isInteger(Number(score)) && Number(score) >= 0 && Number(score) <= 100 && Boolean(assessment);
    });
    submitButton.disabled = !resumeAvailable || !allComplete;
  }

  function markAsManual() {
    if (reviewMethod.value === "AI") {
      reviewMethod.value = "MANUAL";
      feedback.textContent = "AI suggestions edited. This review will be saved as manual.";
    }
  }

  form.addEventListener("input", event => {
    if (event.target.matches(".requirement-score, .review-evidence-field textarea, [name='overall_comments']")) markAsManual();
    updateSubmitState();
  });
  form.addEventListener("change", event => {
    if (event.target.matches(".requirement-assessment")) markAsManual();
    updateSubmitState();
  });

  aiButton?.addEventListener("click", async () => {
    aiButton.disabled = true;
    submitButton.disabled = true;
    aiButton.setAttribute("aria-busy", "true");
    aiButton.classList.add("is-loading");
    if (aiButtonLabel) aiButtonLabel.textContent = "Screening…";
    feedback.classList.remove("is-error");
    feedback.textContent = "Screening the resume and saving the AI results…";
    try {
      const response = await fetch(form.dataset.aiUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken, "Accept": "application/json"},
        body: "{}",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "AI review could not be completed.");

      const resultsByRequirement = new Map((result.criteria_results || []).map(item => [String(item.requirement_id), item]));
      if (resultsByRequirement.size !== rows.length || rows.some(row => !resultsByRequirement.has(row.dataset.requirementId))) {
        throw new Error("AI did not return a result for every requirement. No scores were saved.");
      }
      rows.forEach(row => {
        const item = resultsByRequirement.get(row.dataset.requirementId);
        row.querySelector(".requirement-score").value = item.score ?? "";
        row.querySelector(".requirement-assessment").value = item.assessment ?? "";
        row.querySelector(".review-evidence-field textarea").value = item.evidence ?? "";
      });
      if (commentsInput) commentsInput.value = result.screening_comments || "";
      reviewMethod.value = "AI";
      fileIdInput.value = result.file_id || "";
      if (overallScoreValue && result.score !== null && result.score !== undefined) {
        overallScoreValue.textContent = String(result.score);
        if (overallScoreDisplay) overallScoreDisplay.hidden = false;
      }
      feedback.textContent = "AI screening is saved. The scores are filled below and the application is now in Screened.";
      if (backLink && form.dataset.screenedUrl) {
        backLink.href = form.dataset.screenedUrl;
        backLink.textContent = "Back to Screened";
      }
      updateSubmitState();
    } catch (error) {
      feedback.classList.add("is-error");
      feedback.textContent = error.message || "AI review could not be completed.";
    } finally {
      aiButton.disabled = !resumeAvailable || rows.length === 0;
      aiButton.setAttribute("aria-busy", "false");
      aiButton.classList.remove("is-loading");
      if (aiButtonLabel) aiButtonLabel.textContent = "Use AI to fill scores";
      updateSubmitState();
    }
  });

  updateSubmitState();
})();
