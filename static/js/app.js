// ─── MODAL MANAGEMENT ───────────────────────────────────────────────────────

function openModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('open');
  document.body.style.overflow = '';
}

function closeOnOverlay(event, id) {
  if (event.target === event.currentTarget) closeModal(id);
}

function switchModal(fromId, toId) {
  closeModal(fromId);
  setTimeout(() => openModal(toId), 150);
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(el => el.classList.remove('open'));
    document.body.style.overflow = '';
    // Also close chat on Escape
    closeChat();
  }
});

// ─── TOAST NOTIFICATION ──────────────────────────────────────────────────────

function showToast(message, duration = 2500) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// ─── PAGE LOAD ANIMATION ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.body.style.opacity = '0';
  document.body.style.transition = 'opacity .4s ease';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => { document.body.style.opacity = '1'; });
  });
});

// ─── AI CHATBOT WIDGET ───────────────────────────────────────────────────────

let chatHistory = [];   // [{role: 'user'|'assistant', content: '...'}]
let chatOpen = false;
let chatSending = false;

function toggleChat() {
  chatOpen = !chatOpen;
  const fab = document.getElementById('chatFab');
  const win = document.getElementById('chatWindow');
  if (!fab || !win) return;
  fab.classList.toggle('open', chatOpen);
  win.classList.toggle('open', chatOpen);
  if (chatOpen) {
    setTimeout(() => document.getElementById('chatInput')?.focus(), 250);
    scrollChatToBottom();
  }
}

function closeChat() {
  chatOpen = false;
  document.getElementById('chatFab')?.classList.remove('open');
  document.getElementById('chatWindow')?.classList.remove('open');
}

function scrollChatToBottom() {
  const box = document.getElementById('chatMessages');
  if (box) box.scrollTop = box.scrollHeight;
}

function appendChatMessage(role, text) {
  const box = document.getElementById('chatMessages');
  if (!box) return;
  const wrap = document.createElement('div');
  wrap.className = 'chat-msg ' + (role === 'user' ? 'chat-msg-user' : 'chat-msg-bot');
  wrap.innerHTML = `
    <span class="chat-msg-avatar">${role === 'user' ? '🙂' : '🪔'}</span>
    <div class="chat-bubble"></div>
  `;
  wrap.querySelector('.chat-bubble').textContent = text;
  box.appendChild(wrap);
  scrollChatToBottom();
}

async function sendChatMessage(e) {
  e.preventDefault();
  if (chatSending) return;

  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;

  appendChatMessage('user', message);
  chatHistory.push({ role: 'user', content: message });
  input.value = '';

  const typingEl = document.getElementById('chatTyping');
  typingEl.style.display = 'flex';
  scrollChatToBottom();

  chatSending = true;
  const sendBtn = document.querySelector('.chat-send-btn');
  if (sendBtn) sendBtn.disabled = true;

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history: chatHistory })
    });
    const data = await res.json();

    typingEl.style.display = 'none';

    if (data.success) {
      appendChatMessage('assistant', data.reply);
      chatHistory.push({ role: 'assistant', content: data.reply });
    } else {
      appendChatMessage('assistant', data.reply || "Sorry, something went wrong.");
    }
  } catch (err) {
    typingEl.style.display = 'none';
    appendChatMessage('assistant', "Sorry, I couldn't connect right now. Please try again.");
  } finally {
    chatSending = false;
    if (sendBtn) sendBtn.disabled = false;
    input.focus();
  }
}
