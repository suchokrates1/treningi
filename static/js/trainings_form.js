(function () {
  function toNumber(value) {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function toDate(value) {
    if (!value) {
      return null;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function calculateOccurrences({
    repeatEnabled,
    startValue,
    intervalWeeks,
    repeatUntilValue,
  }) {
    if (!repeatEnabled) {
      return 1;
    }

    if (!startValue || !repeatUntilValue || !intervalWeeks || intervalWeeks <= 0) {
      return null;
    }

    const [datePart, timePart = "00:00"] = startValue.split("T");
    const startDate = toDate(`${datePart}T${timePart}`);
    const repeatUntil = toDate(`${repeatUntilValue}T23:59:59`);

    if (!startDate || !repeatUntil) {
      return null;
    }

    let count = 1;
    const current = new Date(startDate);

    while (true) {
      current.setDate(current.getDate() + intervalWeeks * 7);
      if (current > repeatUntil) {
        break;
      }
      count += 1;
    }

    return count;
  }

  document.addEventListener("DOMContentLoaded", function () {
    const repeatToggle = document.getElementById("repeat-toggle");
    const repeatSection = document.getElementById("repeat-section");
    const repeatFields = document.getElementById("repeat-fields");
    const scheduleButton = document.getElementById("schedule-button");
    const fallbackSubmit = document.getElementById("single-submit-fallback");
    const occurrenceDisplay = document.getElementById("occurrence-count");
    const weekdayDisplay = document.getElementById("weekday-label");
    const dateField = document.getElementById("date");
    const repeatIntervalField = document.getElementById("repeat_interval");
    const repeatUntilField = document.getElementById("repeat_until");

    const weekdayNames = [
      "Poniedziałek",
      "Wtorek",
      "Środa",
      "Czwartek",
      "Piątek",
      "Sobota",
      "Niedziela",
    ];

    function updateRepeatVisibility() {
      if (!repeatToggle) {
        return;
      }
      const enabled = repeatToggle.checked;

      if (repeatSection) {
        repeatSection.classList.toggle("d-none", !enabled);
      }
      if (repeatFields) {
        repeatFields.classList.toggle("d-none", !enabled);
      }
      if (scheduleButton) {
        scheduleButton.classList.toggle("d-none", !enabled);
      }
      if (fallbackSubmit) {
        fallbackSubmit.classList.toggle("d-none", enabled);
      }

      updateOccurrenceCount();
      updateWeekdayLabel();
    }

    function updateOccurrenceCount() {
      if (!occurrenceDisplay) {
        return;
      }

      const intervalWeeks = toNumber(repeatIntervalField ? repeatIntervalField.value : null);
      const startValue = dateField ? dateField.value : null;
      const repeatUntilValue = repeatUntilField ? repeatUntilField.value : null;
      const repeatEnabled = repeatToggle ? repeatToggle.checked : false;

      const occurrences = calculateOccurrences({
        repeatEnabled,
        startValue,
        intervalWeeks,
        repeatUntilValue,
      });

      occurrenceDisplay.textContent = occurrences === null ? "–" : String(occurrences);
    }

    function updateWeekdayLabel() {
      if (!weekdayDisplay) {
        return;
      }

      const repeatEnabled = repeatToggle ? repeatToggle.checked : false;
      if (!repeatEnabled) {
        weekdayDisplay.textContent = "–";
        return;
      }

      const startValue = dateField ? dateField.value : null;
      if (!startValue) {
        weekdayDisplay.textContent = "–";
        return;
      }

      const [datePart] = startValue.split("T");
      if (!datePart) {
        weekdayDisplay.textContent = "–";
        return;
      }

      const parsedDate = toDate(`${datePart}T00:00:00`);
      if (!parsedDate) {
        weekdayDisplay.textContent = "–";
        return;
      }

      const weekdayIndex = (parsedDate.getDay() + 6) % 7;
      const label = weekdayNames[weekdayIndex] || "–";
      weekdayDisplay.textContent = label;
    }

    if (repeatToggle) {
      repeatToggle.addEventListener("change", updateRepeatVisibility);
    }

    [dateField, repeatIntervalField, repeatUntilField].forEach(function (field) {
      if (!field) {
        return;
      }
      field.addEventListener("change", updateOccurrenceCount);
      field.addEventListener("input", updateOccurrenceCount);
    });

    if (dateField) {
      dateField.addEventListener("change", updateWeekdayLabel);
      dateField.addEventListener("input", updateWeekdayLabel);
    }

    updateRepeatVisibility();
  });
})();
