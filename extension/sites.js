// Per-site settings for the chat pages webllm drives in your Chrome.
// Every list is tried in order; driver.js falls back to generic detection
// (visible textarea, "send"/"copy"/"stop" labels) when none match.
// Claude and ChatGPT are deliberately absent.
self.WEBLLM_SITES = {
  qwen: {
    name: "Qwen",
    newChat: "https://chat.qwen.ai/",
    input: ["textarea.message-input-textarea", "textarea"],
    send: ["button.send-button", "button[aria-label='Send']"],
    stop: ["button.stop-button", "button[aria-label='Stop']"],
    copy: ["[class*='copy-response']", ".response-message-footer [class*='copy']"],
    answer: [".response-message-content", "[class*='response-message-content']"],
    loginUrl: "/auth|/login|/signin|/sign_in",
  },
  deepseek: {
    name: "DeepSeek",
    newChat: "https://chat.deepseek.com/",
    input: ["textarea#chat-input", "textarea"],
    send: [],  // no labelled send button: driver.js presses Enter
    stop: [],
    copy: [],
    answer: [".ds-markdown"],
    loginUrl: "/sign_in|/login|/sign_up",
  },
  zai: {
    name: "z.ai",
    newChat: "https://chat.z.ai/",
    input: ["textarea#chat-input", "textarea"],
    send: ["button#send-message-button"],
    // the stop button has no label: a round black button with a small square inside
    stop: ["button.rounded-full:has(> span.rounded-xs)", "button#stop-response-button"],
    copy: ["button.copy-response-button"],
    answer: [".chat-assistant"],
    loginUrl: "/auth|/login|/signin",
  },
  meta: {
    name: "Meta AI",
    newChat: "https://www.meta.ai/",
    input: ["textarea", "div[contenteditable='true']", "input[placeholder^='Ask Meta AI']"],
    send: ["[aria-label='Send message']", "[aria-label='Send']"],
    stop: ["[aria-label='Stop']", "[aria-label='Stop generating']"],
    copy: ["[aria-label='Copy']", "[aria-label='Copy response']"],
    answer: [],
    loginUrl: "/login|/signin",
    loginText: "Log in or sign up to ask Meta AI|Sign in to get started",
  },
};
