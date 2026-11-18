const store = (globalThis.browser ?? globalThis.chrome).storage.local;
const inputs = ['enabled','related','media'].map(id => document.getElementById(id));
const extra = document.getElementById('extra');
const save = document.getElementById('save');
const status = document.getElementById('status');

save.disabled = true;
store.get([...inputs.map(input => input.id), 'extra']).then(settings => {
  for (const input of inputs) input.checked = settings[input.id] !== false;
  extra.value = settings.extra ?? '';
  save.disabled = false;
}, () => { status.textContent = 'Could not load settings'; });

save.addEventListener('click', async () => {
  save.disabled = true;
  try {
    const settings = Object.fromEntries(inputs.map(input => [input.id, input.checked]));
    await store.set({...settings, extra: extra.value});
    status.textContent = 'Rules saved';
  } catch {
    status.textContent = 'Could not save settings';
  } finally {
    save.disabled = false;
  }
});
