// Apply saved font
chrome.storage.sync.get("selectedFont", ({ selectedFont }) => {
  if (!selectedFont) return;
  const style = document.createElement("style");
  style.innerText = `* { font-family: '${selectedFont}' !important; }`;
  document.head.appendChild(style);
});
