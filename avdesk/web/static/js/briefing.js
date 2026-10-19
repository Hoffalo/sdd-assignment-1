// Progressive enhancement only: without JS every section shows and the server
// still validates. The score here is a live preview; the stored score is
// computed by BriefingScorer on submit.
(function () {
  const form = document.getElementById("briefing-form");
  if (!form) return;

  const detailField = document.getElementById("type-detail-field");
  const detailLabel = document.getElementById("type-detail-label");
  const notice = document.getElementById("deadline-notice");

  function selectedType() {
    const checked = form.querySelector("input[name=type_code]:checked");
    return checked || null;
  }

  function showSectionsFor(typeCode) {
    form.querySelectorAll("fieldset[data-type]").forEach(function (section) {
      const owner = section.dataset.type;
      section.hidden = owner !== "" && owner !== typeCode;
    });
  }

  function updateTypeDetail() {
    const type = selectedType();
    const label = type ? type.dataset.detailLabel : "";
    detailField.hidden = !label;
    if (label) detailLabel.textContent = label;
    showSectionsFor(type ? type.value : null);
  }

  function triggerMatches(fieldName, expected) {
    const inputs = Array.from(form.querySelectorAll('[name="' + fieldName + '"]'));
    return inputs.some(function (input) {
      if (input.type === "checkbox" || input.type === "radio") return input.checked && input.value === expected;
      return input.value === expected;
    });
  }

  // Mirrors Question.is_shown on the server, which stays the authority on submit.
  function updateFollowUps() {
    form.querySelectorAll("[data-depends-on]").forEach(function (block) {
      block.hidden = !triggerMatches(block.dataset.dependsOn, block.dataset.dependsValue);
    });
  }

  function isAnswered(block) {
    const inputs = block.querySelectorAll("input, select, textarea");
    return Array.from(inputs).some(function (input) {
      if (input.type === "checkbox" || input.type === "radio") return input.checked;
      return input.value.trim() !== "";
    });
  }

  function updateScore() {
    const visible = Array.from(form.querySelectorAll("[data-question]"))
      .filter(function (block) { return !block.hidden && !block.closest("fieldset").hidden; });
    const answered = visible.filter(isAnswered).length;
    const score = visible.length ? Math.round((100 * answered) / visible.length) : 0;
    document.getElementById("score-value").textContent = score + "%";
    document.getElementById("score-bar").style.width = score + "%";
  }

  function updateDeadline() {
    const type = selectedType();
    const neededBy = form.querySelector("[name=needed_by]").value;
    if (!type || !neededBy) { notice.hidden = true; return; }
    const params = new URLSearchParams({
      type_code: type.value,
      needed_by: neededBy,
      needs_c_level_approval: form.querySelector("[name=needs_c_level_approval]").checked ? "sim" : "",
    });
    fetch(form.dataset.deadlineUrl + "?" + params)
      .then(function (response) { return response.json(); })
      .then(function (result) {
        if (result.rush === undefined) { notice.hidden = true; return; }
        notice.hidden = false;
        notice.classList.toggle("notice-rush", result.rush);
        notice.textContent = result.rush
          ? "Prazo curto: esse tipo de vídeo pede " + result.required_days + " dias e você deu " +
            result.available_days + ". A data mais realista é " + result.earliest_date +
            ". Você ainda pode enviar, explicando abaixo por que a data não pode mudar."
          : "Prazo ok: " + result.available_days + " dias até a entrega.";
      })
      .catch(function () { notice.hidden = true; });
  }

  form.addEventListener("change", function (event) {
    if (["type_code", "needed_by", "needs_c_level_approval"].includes(event.target.name)) {
      updateTypeDetail();
      updateDeadline();
    }
    updateFollowUps();
    updateScore();
  });
  form.addEventListener("input", updateScore);

  updateTypeDetail();
  updateFollowUps();
  updateDeadline();
  updateScore();
})();
