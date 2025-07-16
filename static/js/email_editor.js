window.addEventListener('DOMContentLoaded', () => {
  const editors = {};

  function init(fieldId, editorId) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    const quill = new Quill('#' + editorId, {
      theme: 'snow',
      modules: {
        toolbar: [
          ['bold', 'italic', 'underline'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link']
        ]
      }
    });
    quill.root.innerHTML = field.value || '';
    editors[editorId] = quill;

    const textarea = document.getElementById(editorId + '_textarea');
    const toggleSwitch = document.querySelector(
      '.html-toggle-switch[data-editor="' + editorId + '"]'
    );
    const container = document.getElementById(editorId);

    function updateMode() {
      if (toggleSwitch.checked) {
        textarea.value = quill.root.innerHTML;
        textarea.classList.remove('d-none');
        container.classList.add('d-none');
      } else {
        quill.clipboard.dangerouslyPasteHTML(textarea.value);
        textarea.classList.add('d-none');
        container.classList.remove('d-none');
      }
    }

    if (toggleSwitch && textarea) {
      toggleSwitch.addEventListener('change', updateMode);
      updateMode();
    }

    field.closest('form').addEventListener('submit', () => {
      if (textarea && !textarea.classList.contains('d-none')) {
        field.value = textarea.value;
      } else {
        field.value = quill.root.innerHTML;
      }
    });
  }

  init('registration_template', 'registration_editor');
  init('cancellation_template', 'cancellation_editor');

  document.querySelectorAll('.insert-var').forEach(btn => {
    btn.addEventListener('click', () => {
      const editorId = btn.dataset.editor;
      const editor = editors[editorId];
      if (!editor) return;
      const val = btn.dataset.value || '';
      const textarea = document.getElementById(editorId + '_textarea');
      if (textarea && !textarea.classList.contains('d-none')) {
        const start = textarea.selectionStart || textarea.value.length;
        const end = textarea.selectionEnd || start;
        textarea.setRangeText(val, start, end, 'end');
        textarea.focus();
      } else {
        const range = editor.getSelection(true);
        const index = range ? range.index : editor.getLength();
        editor.insertText(index, val);
        editor.setSelection(index + val.length);
      }
    });
  });

  document.querySelectorAll('.preview-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const editorId = btn.dataset.editor;
      const editor = editors[editorId];
      if (!editor) return;
      const textarea = document.getElementById(editorId + '_textarea');
      const content = textarea && !textarea.classList.contains('d-none')
        ? textarea.value
        : editor.root.innerHTML;
      fetch(`/admin/settings/preview/${btn.dataset.template}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ content })
      })
        .then(resp => resp.text())
        .then(snippet => {
          const modal = document.getElementById('previewModal');
          if (!modal) return;
          modal.querySelector('.modal-body').innerHTML = snippet;
          new bootstrap.Modal(modal).show();
        });
    });
  });
});
