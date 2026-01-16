


// workshop_editor.js - 工坊创作页面交互
// 依赖：页面需通过<script src="/static/js/socket.io.min.js"></script>引入socket.io客户端
// 优化：页面加载即建立socket.io连接，保存草稿后join房间，支持断线重连

// ========== 自动加载最近草稿 ===========

window.addEventListener('DOMContentLoaded', function() {
  console.log('[workshop_editor] DOMContentLoaded fired, 自动加载草稿逻辑开始');
  // 只在初次加载时自动填充
  fetch('/workshop/my_drafts', {
    method: 'GET',
    credentials: 'include'
  })
    .then(r => {
      console.log('[workshop_editor] /workshop/my_drafts fetch响应', r);
      return r.json();
    })
    .then(res => {
      console.log('[workshop_editor] /workshop/my_drafts 响应内容', res);
      if (res.success && res.drafts && res.drafts.length > 0) {
        // 取最近一条
        const draft = res.drafts[0];
        fetch(`/workshop/draft/${draft.id}`, {
          method: 'GET',
          credentials: 'include'
        })
          .then(r2 => {
            console.log('[workshop_editor] /workshop/draft/<id> fetch响应', r2);
            return r2.json();
          })
          .then(res2 => {
            console.log('[workshop_editor] /workshop/draft/<id> 响应内容', res2);
            if (res2.success && res2.draft) {
              // 填充表单
              const form = document.getElementById('workshop-form');
              form.title.value = res2.draft.title || '';
              form.description.value = res2.draft.description || '';
              form.content.value = res2.draft.content || '';
              // 设置创作方式
              if (res2.draft.type === 'upload') {
                form.mode.value = 'upload';
                document.getElementById('online-editor').classList.add('d-none');
                document.getElementById('upload-area').classList.remove('d-none');
              } else {
                form.mode.value = 'online';
                document.getElementById('online-editor').classList.remove('d-none');
                document.getElementById('upload-area').classList.add('d-none');
              }
            }
          });
      }
    });
  console.log('[workshop_editor] 自动加载草稿逻辑结束');
});


let socket = null;
let joinedRoom = null;
function getSocketUrl() {
  // 生产环境用固定域名，开发用本地
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return undefined; // 默认即可
  }
  // 生产环境
  return 'wss://67656.fun';
}
function ensureSocketConnected() {
  if (!window.io) return null;
  if (socket && socket.connected) return socket;
  // 健壮参数：自动重连、降级、心跳、最大缓冲、路径、日志
  socket = io(getSocketUrl(), {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    pingTimeout: 30000,
    pingInterval: 10000,
    autoConnect: true,
    path: '/socket.io',
    upgrade: true,
    withCredentials: true,
    forceNew: true,
    allowUpgrades: true,
    transportsOptions: {
      polling: { extraHeaders: { 'X-Requested-With': 'XMLHttpRequest' } }
    },
    maxHttpBufferSize: 10 * 1024 * 1024,
    debug: true
  });
  socket.on('disconnect', (reason) => {
    console.warn('Socket disconnected:', reason);
    // 自动重连
    if (socket && !socket.connected) {
      setTimeout(() => {
        if (socket && !socket.connected) {
          socket.connect();
          if (joinedRoom) {
            socket.emit('join', { room: joinedRoom });
          }
        }
      }, 1000);
    }
  });
  socket.on('connect_error', (err) => {
    console.error('Socket connect_error:', err);
  });
  socket.on('reconnect_attempt', (attempt) => {
    console.info('Socket reconnect attempt:', attempt);
  });
  socket.on('reconnect_failed', () => {
    console.error('Socket reconnect failed.');
  });
  socket.on('error', (err) => {
    console.error('Socket error:', err);
  });
  return socket;
}


document.getElementById('save-btn').onclick = function() {
  const form = document.getElementById('workshop-form');
  const saveBtn = document.getElementById('save-btn');
  saveBtn.disabled = true;
  saveBtn.innerText = '保存中...';
  if (!sessionStorage.getItem('draft_save_tip')) {
    alert('首次保存可能较慢，请耐心等待，后续将更快。');
    sessionStorage.setItem('draft_save_tip', '1');
  }
  // 自动重试机制
  let retryCount = 2;
  function trySave() {
    // 先 join 房间（用 user_id+title 作为房间名，保证推送不丢失）
    const userId = window.currentUserId || (window.user && window.user.id);
    const title = form.title.value.trim();
    const roomName = userId && title ? `${userId}_${title}` : undefined;
    const s = ensureSocketConnected();
    if (s && roomName) {
      s.emit('join', { room: roomName });
      joinedRoom = roomName;
      console.log('[save-btn] join房间(预生成)', roomName);
    }
    saveDraftWithSocketReady(form, (success) => {
      if (success) {
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
      } else if (retryCount > 0) {
        alert('网络波动，正在自动重试...');
        retryCount--;
        trySave();
      } else {
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
        alert('保存失败，请稍后重试。');
      }
    }, roomName);
  }
  const s = ensureSocketConnected();
  if (s && s.connected) {
    console.log('[save-btn] socketio已连接，立即提交保存');
    trySave();
  } else {
    console.warn('[save-btn] socketio未连接，等待连接ready后再提交保存...');
    if (s) {
      const onConnect = () => {
        console.log('[save-btn] socketio已连接，自动提交保存');
        s.off('connect', onConnect);
        trySave();
      };
      s.on('connect', onConnect);
      if (!s.connected) s.connect();
    } else {
      alert('socket.io 客户端未加载，无法保存！');
      saveBtn.disabled = false;
      saveBtn.innerText = '保存草稿';
    }
  }
};

// 原保存草稿逻辑，抽出为独立函数
function saveDraftWithSocketReady(form) {

  let valid = true;
  // 校验必填项
  // 标题
  if (!form.title.value.trim()) {
    form.title.classList.add('is-invalid');
    form.title.focus();
    form.title.setCustomValidity('请填写此字段');
    valid = false;
  } else {
    form.title.classList.remove('is-invalid');
    form.title.setCustomValidity('');
  }
  // 创作方式

  const mode = form.mode.value;
  if (mode === 'online') {
    // 正文内容必填
    if (!form.content.value.trim()) {
      form.content.classList.add('is-invalid');
      form.content.focus();
      form.content.setCustomValidity('请填写此字段');
      valid = false;
    } else {
      form.content.classList.remove('is-invalid');
      form.content.setCustomValidity('');
    }
    // 切换到在线编辑时清空上传区
    form.file.value = '';
  } else if (mode === 'upload') {
    // 文件必选
    if (!form.file.value) {
      form.file.classList.add('is-invalid');
      form.file.focus();
      form.file.setCustomValidity('请填写此字段');
      valid = false;
    } else {
      form.file.classList.remove('is-invalid');
      form.file.setCustomValidity('');
    }
    // 切换到上传时清空在线内容
    form.content.value = '';
  }
  if (!valid) {
    return;
  }

  // 上传文件模式下自动读取文件内容填充到content
  function doSaveWithContent(contentStr, callback) {
    console.log('[save-btn] 开始提交保存草稿...');
    const data = {
      title: form.title.value,
      description: form.description.value,
      mode: form.mode.value,
      content: contentStr
    };
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    let csrfToken = csrfInput ? csrfInput.value : '';
    csrfToken = csrfToken.replace(/^"|"$/g, '');
    console.log('CSRF Token:', csrfToken);
    fetch('/workshop/save_draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(data),
      credentials: 'include'
    }).then(async r => {
      console.log('[save-btn] 保存草稿请求已返回，处理响应...');
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('text/html')) {
        const html = await r.text();
        alert('未登录或CSRF校验失败！\n' + html.slice(0, 200));
        // 兜底恢复按钮
        const saveBtn = document.getElementById('save-btn');
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
        callback(false);
        return {};
      }
      try {
        return await r.json();
      } catch (e) {
        alert('响应不是JSON，可能后端异常！');
        // 兜底恢复按钮
        const saveBtn = document.getElementById('save-btn');
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
        callback(false);
        return {};
      }
    }).then(res => {
      console.log('[save-btn] 保存草稿响应：', res);
      // fetch成功后立即恢复按钮，无论socketio消息如何
      const saveBtn = document.getElementById('save-btn');
      saveBtn.disabled = false;
      saveBtn.innerText = '保存草稿';
      if (res.success && res.task_id) {
        const s = ensureSocketConnected();
        if (s) {
          joinedRoom = res.task_id;
          console.log('[save-btn] join房间', res.task_id);
          s.emit('join', { room: res.task_id });
          if (!s._workshopDraftStatusHandler) {
            console.log('[save-btn] 注册socketio draft_status事件监听');
            s._workshopDraftStatusHandler = function(msg) {
              console.log('[save-btn] 收到socketio draft_status推送：', msg);
              if (msg.status === 'done') {
                updateStats(msg.stats || {});
                alert(msg.msg || '草稿已保存');
                if (typeof callback === 'function') callback(true);
                return;
              }
              if (msg.status === 'error') {
                alert('保存失败：' + (msg.msg || '未知错误'));
                if (typeof callback === 'function') callback(false);
                updateStats(msg.stats || {});
                return;
              }
              if (msg.status === 'processing') {
                // 可选：显示进度
              }
            };
            s.on('draft_status', s._workshopDraftStatusHandler);
          }
        }
      } else {
        callback(false);
      }
    });
  }

  if (mode === 'upload') {
    // 读取文件内容（支持pdf/docx/txt/md）
    const file = form.file.files[0];
    if (file) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (['pdf', 'docx', 'txt', 'md'].includes(ext)) {
        // 用FormData上传到后端解析
        const fd = new FormData();
        fd.append('file', file);
        fetch('/workshop/upload_file', {
          method: 'POST',
          body: fd,
          credentials: 'include'
        })
          .then(async r => {
            const ct = r.headers.get('content-type') || '';
            if (ct.includes('application/json')) {
              try {
                return await r.json();
              } catch (e) {
                alert('后端返回内容不是有效JSON，可能服务异常！');
                return {};
              }
            } else {
              // 可能是未登录/CSRF/500等，返回HTML
              const html = await r.text();
              alert('文件上传/解析失败，后端返回：\n' + html.slice(0, 300));
              return {};
            }
          })
          .then(res => {
            if (res.success && typeof res.content === 'string') {
              form.content.value = res.content;
              doSaveWithContent(res.content);
            } else if (res.msg) {
              alert('文件解析失败：' + res.msg);
            }
          })
          .catch(e => {
            alert('文件上传/解析异常：' + e);
          });
      } else {
        alert('仅支持txt, md, pdf, docx文件');
      }
    }
  } else {
    doSaveWithContent(form.content.value);
  }



// 页面加载即建立socket连接，便于后续join房间
ensureSocketConnected();

function updateStats(stats) {
  document.getElementById('stat-words').textContent = stats.words || 0
  document.getElementById('stat-cn').textContent = stats.cn_chars || 0
  document.getElementById('stat-en').textContent = stats.en_words || 0
  document.getElementById('stat-rich').textContent = stats.richness || 0
  // 高频词渲染修复
  let topWordsArr = [];
  if (typeof stats.top_words === 'string') {
    try {
      topWordsArr = JSON.parse(stats.top_words);
    } catch (e) {
      topWordsArr = [];
    }
  } else if (Array.isArray(stats.top_words)) {
    topWordsArr = stats.top_words;
  }
  document.getElementById('stat-top').textContent = topWordsArr.length
    ? topWordsArr.map(w => `${w.word}(${w.freq ?? w.count ?? 0})`).join(', ')
    : '';
  // 敏感词渲染（同理，支持字符串或数组）
  let sensitiveArr = [];
  if (typeof stats.sensitive_words === 'string') {
    try {
      sensitiveArr = JSON.parse(stats.sensitive_words);
    } catch (e) {
      sensitiveArr = [];
    }
  } else if (Array.isArray(stats.sensitive_words)) {
    sensitiveArr = stats.sensitive_words;
  }
  document.getElementById('stat-sensitive').textContent = sensitiveArr.length
    ? sensitiveArr.map(w => (typeof w === 'string' ? w : w.word || '')).filter(Boolean).join(', ')
    : '';
  // 章节目录
  const sectionList = document.getElementById('section-list')
  sectionList.innerHTML = ''
  console.log('接口返回sections:', stats.sections);
  if (Array.isArray(stats.sections)) {
    // 跳过Introduction或将其排在最后，排序1从第一个内容标题开始
    const normalSections = stats.sections.filter(sec => sec.title !== 'Introduction');
    let order = 1;
    normalSections.forEach(sec => {
      const li = document.createElement('li');
      // 显示章节名和内容占比（百分比，保留1位小数）
      let ratioStr = '';
      if (typeof sec.ratio === 'number') {
        ratioStr = '（占比 ' + (sec.ratio * 100).toFixed(1) + '%）';
      }
      li.textContent = (order++) + '. ' + (sec.title || '章节') + ratioStr;
      sectionList.appendChild(li);
    });
    // 如需显示Introduction，可排在最后
    const intro = stats.sections.find(sec => sec.title === 'Introduction');
    if (intro) {
      const li = document.createElement('li');
      let ratioStr = '';
      if (typeof intro.ratio === 'number') {
        ratioStr = '（占比 ' + (intro.ratio * 100).toFixed(1) + '%）';
      }
      li.textContent = '（未分章节内容）' + ratioStr;
      sectionList.appendChild(li);
    }
  }
}
}