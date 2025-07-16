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
    field.closest('form').addEventListener('submit', () => {
      field.value = quill.root.innerHTML;
    });
  }

  init('registration_template', 'registration_editor');
  init('cancellation_template', 'cancellation_editor');

  document.querySelectorAll('.insert-var').forEach(btn => {
    btn.addEventListener('click', () => {
      const editor = editors[btn.dataset.editor];
      if (!editor) return;
      const val = btn.dataset.value || '';
      const range = editor.getSelection(true);
      const index = range ? range.index : editor.getLength();
      editor.insertText(index, val);
      editor.setSelection(index + val.length);
    });
  });

  document.querySelectorAll('.preview-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const editor = editors[btn.dataset.editor];
      if (!editor) return;
      const content = editor.root.innerHTML;
      fetch(`/admin/settings/preview/${btn.dataset.template}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ content })
      })
        .then(resp => resp.text())
        .then(html => {
          const w = window.open('', '_blank');
          if (w) {
            w.document.write(html);
            w.document.close();
          }
        });
    });
  });
});
