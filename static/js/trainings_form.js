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
    const dateField = document.getElementById("date");
    const repeatIntervalField = document.getElementById("repeat_interval");
    const repeatUntilField = document.getElementById("repeat_until");
    const locationField = document.getElementById("location_id");
    const coachField = document.getElementById("coach_id");
    const maxVolunteersField = document.getElementById("max_volunteers");

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

    function buildScheduleUrl() {
      if (!scheduleButton) {
        return null;
      }
      const baseUrl = scheduleButton.getAttribute("data-schedule-url");
      if (!baseUrl) {
        return null;
      }

      const url = new URL(baseUrl, window.location.origin);

      if (dateField && dateField.value) {
        const [startDatePart, startTimePart = ""] = dateField.value.split("T");
        if (startDatePart) {
          url.searchParams.set("start_date", startDatePart);
          const weekday = toDate(`${startDatePart}T00:00:00`);
          if (weekday) {
            const pythonWeekday = (weekday.getDay() + 6) % 7;
            url.searchParams.append("days", String(pythonWeekday));
          }
        }
        if (startTimePart) {
          url.searchParams.set("start_time", startTimePart);
        }
      }

      if (repeatIntervalField && repeatIntervalField.value) {
        url.searchParams.set("interval_weeks", repeatIntervalField.value);
      }

      if (repeatUntilField && repeatUntilField.value) {
        url.searchParams.set("end_date", repeatUntilField.value);
      }

      if (locationField && locationField.value) {
        url.searchParams.set("location_id", locationField.value);
      }

      if (coachField && coachField.value) {
        url.searchParams.set("coach_id", coachField.value);
      }

      if (maxVolunteersField && maxVolunteersField.value) {
        url.searchParams.set("max_volunteers", maxVolunteersField.value);
      }

      return url;
    }

    if (repeatToggle) {
      repeatToggle.addEventListener("change", updateRepeatVisibility);
    }

    const scheduleClickHandler = function (event) {
      const url = buildScheduleUrl();
      if (!url) {
        return;
      }
      event.preventDefault();
      window.location.href = url.toString();
    };

    if (scheduleButton) {
      scheduleButton.addEventListener("click", scheduleClickHandler);
    }

    [dateField, repeatIntervalField, repeatUntilField].forEach(function (field) {
      if (!field) {
        return;
      }
      field.addEventListener("change", updateOccurrenceCount);
      field.addEventListener("input", updateOccurrenceCount);
    });

    updateRepeatVisibility();
  });
})();
