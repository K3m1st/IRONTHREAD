// Content script - runs on every page
console.log("Content script loaded on: " + window.location.href);

// Grab cookies and page content
console.log("[COOKIES] " + document.cookie);
console.log("[URL] " + window.location.href);
console.log("[TITLE] " + document.title);

// Check for forms with credentials
const inputs = document.querySelectorAll('input[type="password"], input[type="text"], input[type="email"]');
inputs.forEach(inp => {
  console.log(`[INPUT] name=${inp.name} value=${inp.value} type=${inp.type}`);
});
