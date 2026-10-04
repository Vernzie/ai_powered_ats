(() => {
  const page = document.getElementById("interview-preparation");
  const applicationSelect = document.getElementById("interview-application-select");
  const applicationPicker = document.getElementById("interview-application-picker");
  const applicationOptions = document.getElementById("interview-application-options");
  const questionList = document.getElementById("interview-question-list");
  const addQuestionButton = document.getElementById("add-interview-question");
  const generateQuestionsButton = document.getElementById("generate-interview-questions");
  const generateQuestionsLabel = document.getElementById("generate-interview-questions-label");
  const aiPrompt = document.getElementById("interview-ai-prompt");
  const aiQuestionCount = document.getElementById("interview-ai-question-count");
  const aiFeedback = document.getElementById("interview-ai-feedback");
  const dataElement = document.getElementById("interview-question-data");
  if (!page || !questionList || !addQuestionButton || !generateQuestionsButton || !dataElement) return;

  const csrfToken = document.querySelector('#interview-csrf-token [name="csrfmiddlewaretoken"]')?.value
    || document.cookie.split("; ").find(row => row.startsWith("csrftoken="))?.split("=")[1]
    || "";
  const createUrl = page.dataset.createQuestionUrl;
  const questionUrlTemplate = page.dataset.questionUrlTemplate;
  const generateQuestionsUrl = page.dataset.generateQuestionsUrl;
  applicationSelect?.addEventListener("click", () => {
    const isExpanded = applicationSelect.getAttribute("aria-expanded") === "true";
    applicationSelect.setAttribute("aria-expanded", String(!isExpanded));
    applicationOptions.hidden = isExpanded;
  });
  applicationSelect?.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      applicationSelect.setAttribute("aria-expanded", "false");
      applicationOptions.hidden = true;
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      applicationSelect.setAttribute("aria-expanded", "true");
      applicationOptions.hidden = false;
      applicationOptions.querySelector('[role="option"]')?.focus();
    }
  });
  applicationOptions?.addEventListener("click", event => {
    const option = event.target.closest('[role="option"]');
    if (option?.dataset.applicationUrl) window.location.assign(option.dataset.applicationUrl);
  });
  document.addEventListener("click", event => {
    if (applicationPicker?.contains(event.target)) return;
    if (!applicationSelect || !applicationOptions) return;
    applicationSelect.setAttribute("aria-expanded", "false");
    applicationOptions.hidden = true;
  });
  let nextLocalId = 1;
  let questions = JSON.parse(dataElement.textContent).map(question => ({
    ...question,
    saved: true,
    editing: false,
    saving: false,
    menuOpen: false,
    error: "",
  }));

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));

  function newDraft() {
    return {
      localId: nextLocalId++,
      id: null,
      question: "",
      expected_answer: "",
      question_type: "GENERAL",
      weight: 1,
      saved: false,
      editing: true,
      saving: false,
      menuOpen: false,
      error: "",
    };
  }

  function renderQuestionCard(question, index) {
    const saved = question.saved;
    const editing = question.editing;
    const key = question.id || `draft-${question.localId}`;
    const questionUrl = questionUrlTemplate.replace(/\/0\/$/, `/${question.id}/`);
    return `
      <article class="interview-question-card" data-question-key="${key}">
        <div class="interview-question-card-heading">
          <strong>Question ${index + 1}</strong>
          ${saved && !editing ? `
            <div class="interview-question-actions">
              <button type="button" class="interview-question-menu-toggle" data-action="toggle-menu" aria-label="Question ${index + 1} options" aria-expanded="${question.menuOpen}">&#8942;</button>
              <div class="interview-question-menu" ${question.menuOpen ? "" : "hidden"}>
                <button type="button" data-action="edit">Edit</button>
                <button type="button" data-action="remove">Remove</button>
              </div>
            </div>
          ` : ""}
        </div>
        ${saved && !editing ? `
          <div class="interview-question-summary">
            <p>${escapeHtml(question.question)}</p>
            <small>${question.question_type === "SPECIFIC" ? "Specific" : "General"} · Weight ${question.weight}</small>
            ${question.expected_answer ? `<div class="interview-question-expected"><strong>Expected response or answer</strong><p>${escapeHtml(question.expected_answer)}</p></div>` : ""}
          </div>
        ` : `
          <div class="interview-question-fields">
            <label class="interview-question-field">Question type
              <select data-field="question_type" ${question.saving ? "disabled" : ""}>
                <option value="GENERAL" ${question.question_type === "GENERAL" ? "selected" : ""}>General</option>
                <option value="SPECIFIC" ${question.question_type === "SPECIFIC" ? "selected" : ""}>Specific</option>
              </select>
            </label>
            <label class="interview-question-field">Weight
              <input data-field="weight" type="number" min="1" max="65535" step="1" value="${escapeHtml(question.weight)}" ${question.saving ? "disabled" : ""}>
            </label>
          </div>
          <label class="interview-question-field">Question
            <textarea data-field="question" placeholder="Write an interview question" ${question.saving ? "disabled" : ""}>${escapeHtml(question.question)}</textarea>
          </label>
          <label class="interview-question-field">Expected response or answer <span class="interview-question-optional">Optional</span>
            <textarea data-field="expected_answer" placeholder="What would a strong response include?" ${question.saving ? "disabled" : ""}>${escapeHtml(question.expected_answer)}</textarea>
          </label>
          ${question.error ? `<p class="interview-question-error" role="alert">${escapeHtml(question.error)}</p>` : ""}
          <div class="interview-question-edit-actions">
            <button type="button" class="interview-question-save" data-action="save" ${question.saving ? "disabled" : ""}>${question.saving ? "Saving…" : saved ? "Save changes" : "Save question"}</button>
            <button type="button" class="interview-question-cancel" data-action="cancel" ${question.saving ? "disabled" : ""}>${saved ? "Cancel" : "Remove draft"}</button>
          </div>
        `}
      </article>
    `;
  }

  function render() {
    questionList.innerHTML = questions.map(renderQuestionCard).join("");
  }

  function readQuestionFromCard(card) {
    const text = card.querySelector('[data-field="question"]').value.trim();
    const expectedAnswer = card.querySelector('[data-field="expected_answer"]').value.trim();
    const questionType = card.querySelector('[data-field="question_type"]').value;
    const weightValue = card.querySelector('[data-field="weight"]').value;
    const weight = Number(weightValue);
    if (!text) return { error: "Enter a question." };
    if (!["GENERAL", "SPECIFIC"].includes(questionType)) return { error: "Choose a valid question type." };
    if (!Number.isInteger(weight) || weight < 1 || weight > 65535) return { error: "Weight must be a whole number from 1 to 65535." };
    return { data: { question: text, expected_answer: expectedAnswer, question_type: questionType, weight } };
  }

  function getQuestionFromCard(card, question) {
    const result = readQuestionFromCard(card);
    if (result.error) return result;
    Object.assign(question, result.data);
    return result;
  }

  async function saveQuestion(question, card) {
    const parsed = getQuestionFromCard(card, question);
    if (parsed.error) {
      question.error = parsed.error;
      render();
      return;
    }

    question.saving = true;
    question.error = "";
    render();
    const isSaved = question.saved;
    const url = isSaved ? questionUrlTemplate.replace(/\/0\/$/, `/${question.id}/`) : createUrl;
    try {
      const response = await fetch(url, {
        method: isSaved ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, "Accept": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "The question could not be saved.");
      Object.assign(question, result, { saved: true, editing: false, saving: false, menuOpen: false, error: "" });
    } catch (error) {
      question.saving = false;
      question.error = error.message || "The question could not be saved.";
    }
    render();
  }

  async function removeQuestion(question) {
    if (!question.saved) {
      questions = questions.filter(item => item !== question);
      render();
      return;
    }
    if (!window.confirm("Remove this saved interview question?")) return;
    question.saving = true;
    question.error = "";
    render();
    const url = questionUrlTemplate.replace(/\/0\/$/, `/${question.id}/`);
    try {
      const response = await fetch(url, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfToken, "Accept": "application/json" },
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "The question could not be removed.");
      questions = questions.filter(item => item !== question);
    } catch (error) {
      question.saving = false;
      question.error = error.message || "The question could not be removed.";
    }
    render();
  }

  addQuestionButton.addEventListener("click", () => {
    const cards = [...questionList.querySelectorAll(".interview-question-card")];
    for (const [index, question] of questions.entries()) {
      if ((question.saved && !question.editing) || question.saving) continue;
      const result = readQuestionFromCard(cards[index]);
      if (result.error) {
        question.error = result.error;
        render();
        questionList.querySelectorAll(".interview-question-card")[index]
          ?.querySelector('[data-field="question"]')
          ?.focus();
        return;
      }
    }
    questions.push(newDraft());
    render();
  });
  generateQuestionsButton.addEventListener("click", async () => {
    const prompt = aiPrompt.value.trim();
    const questionCount = Number(aiQuestionCount.value);
    if (!prompt) {
      aiFeedback.textContent = "Enter instructions for the AI first.";
      aiFeedback.classList.add("is-error");
      aiPrompt.focus();
      return;
    }
    if (!Number.isInteger(questionCount) || questionCount < 1 || questionCount > 20) {
      aiFeedback.textContent = "Choose a whole number of questions from 1 to 20.";
      aiFeedback.classList.add("is-error");
      aiQuestionCount.focus();
      return;
    }

    generateQuestionsButton.disabled = true;
    generateQuestionsButton.setAttribute("aria-busy", "true");
    generateQuestionsButton.classList.add("is-loading");
    generateQuestionsLabel.textContent = "Generating…";
    aiFeedback.classList.remove("is-error");
    aiFeedback.textContent = "Reviewing the resume and generating questions…";
    try {
      const response = await fetch(generateQuestionsUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, "Accept": "application/json" },
        body: JSON.stringify({ prompt, question_count: questionCount }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "AI question generation failed.");
      if (!Array.isArray(result.questions) || result.questions.length === 0) {
        throw new Error("The AI did not return any saved questions.");
      }
      questions.push(...result.questions.map(question => ({
        ...question,
        saved: true,
        editing: false,
        saving: false,
        menuOpen: false,
        error: "",
      })));
      render();
      aiFeedback.textContent = `${result.questions.length} questions generated and saved.`;
    } catch (error) {
      aiFeedback.classList.add("is-error");
      aiFeedback.textContent = error.message || "AI question generation failed.";
    } finally {
      generateQuestionsButton.disabled = false;
      generateQuestionsButton.setAttribute("aria-busy", "false");
      generateQuestionsButton.classList.remove("is-loading");
      generateQuestionsLabel.textContent = "Generate questions";
    }
  });
  questionList.addEventListener("click", event => {
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) return;
    const card = actionButton.closest(".interview-question-card");
    const key = card?.dataset.questionKey;
    const question = questions.find(item => String(item.id || `draft-${item.localId}`) === key);
    if (!question) return;

    if (actionButton.dataset.action === "toggle-menu") {
      question.menuOpen = !question.menuOpen;
      render();
    } else if (actionButton.dataset.action === "edit") {
      question.editing = true;
      question.menuOpen = false;
      render();
    } else if (actionButton.dataset.action === "save") {
      saveQuestion(question, card);
    } else if (actionButton.dataset.action === "cancel") {
      if (question.saved) {
        question.editing = false;
        question.error = "";
      } else {
        questions = questions.filter(item => item !== question);
      }
      render();
    } else if (actionButton.dataset.action === "remove") {
      removeQuestion(question);
    }
  });

  document.addEventListener("click", event => {
    if (event.target.closest(".interview-question-actions")) return;
    const openMenus = questions.filter(question => question.menuOpen);
    if (!openMenus.length) return;
    openMenus.forEach(question => { question.menuOpen = false; });
    render();
  });

  if (!questions.length) questions.push(newDraft());
  render();
})();
