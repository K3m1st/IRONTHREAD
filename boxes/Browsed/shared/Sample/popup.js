const fontSelector = document.getElementById("fontSelector");

chrome.storage.sync.get("selectedFont", ({ selectedFont }) => {
  if (selectedFont) {
    fontSelector.value = selectedFont;
  }
});

fontSelector.addEventListener("change", () => {
  const selectedFont = fontSelector.value;
  chrome.storage.sync.set({ selectedFont }, () => {
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        func: (font) => {
          const style = document.createElement("style");
          style.innerText = `* { font-family: '${font}' !important; }`;
          document.head.appendChild(style);
        },
        args: [selectedFont]
      });
    });
  });
});
