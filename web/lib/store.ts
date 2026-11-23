// Approved profiles live in this browser only. Every access is guarded: storage can be
// unavailable (private mode, blocked site data) and the app must still work.
const KEY = "aikeel.profiles.v1";
let memory: Record<string, string> = {};

function read(): Record<string, string> {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) memory = JSON.parse(raw);
  } catch {}
  return memory;
}

function write(all: Record<string, string>) {
  memory = all;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(all));
  } catch {}
}

export const profiles = {
  all: () => ({ ...read() }),
  get: (id: string): string | undefined => read()[id],
  set: (id: string, yaml: string) => write({ ...read(), [id]: yaml }),
  remove: (id: string) => {
    const a = { ...read() };
    delete a[id];
    write(a);
  },
};

// The demo customer that gets onboarded live, and reset between visitors.
export const DEMO_CUSTOMER = "hidden_c";
