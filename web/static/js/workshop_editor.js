

// workshop_editor.js - 工坊创作页面交互
// 依赖：页面需通过<script src="/static/js/socket.io.min.js"></script>引入socket.io客户端
// 优化：页面加载即建立socket.io连接，保存草稿后join房间，支持断线重连


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
  socket = io(getSocketUrl(), { transports: ['websocket'] });
  socket.on('disconnect', () => {
    // 自动重连
    setTimeout(() => {
      socket.connect();
      if (joinedRoom) {
        socket.emit('join', { room: joinedRoom });
      }
    }, 1000);
  });
  return socket;
}

document.getElementById('save-btn').onclick = function() {

  const form = document.getElementById('workshop-form');
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
  function doSaveWithContent(contentStr) {
    const data = {
      title: form.title.value,
      description: form.description.value,
      mode: form.mode.value,
      content: contentStr
    };
    // ...existing code for CSRF, fetch, socket, etc...
    // 获取 CSRF Token（优先从 DOM input[name=csrf_token] 读取）
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    let csrfToken = csrfInput ? csrfInput.value : '';
    csrfToken = csrfToken.replace(/^"|"$/g, '');
    console.log('CSRF Token:', csrfToken); // 调试输出

    fetch('/workshop/save_draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(data),
      credentials: 'include'
    }).then(async r => {
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('text/html')) {
        const html = await r.text();
        alert('未登录或CSRF校验失败！\n' + html.slice(0, 200));
        return {};
      }
      try {
        return await r.json();
      } catch (e) {
        alert('响应不是JSON，可能后端异常！');
        return {};
      }
    }).then(res => {
      if (res.success && res.task_id) {
        // 页面已建立socket连接，保存后join房间
        const s = ensureSocketConnected();
        if (s) {
          joinedRoom = res.task_id;
          console.log('Joining room', res.task_id);
          s.emit('join', { room: res.task_id });
          // 只注册一次事件
          if (!s._workshopDraftStatusHandler) {
            s._workshopDraftStatusHandler = function(msg) {
              // 实时推送统计/状态
              if (msg.stats) {
                // 优先使用 socket 推送的最新统计，防止 analyze 覆盖
                updateStats(msg.stats);
                if (msg.status === 'done' && msg.id) {
                  alert(msg.msg || '草稿已保存');
                } else if (msg.status === 'error') {
                  alert('保存失败：' + (msg.msg || '未知错误'));
                }
                return; // 有 stats 时不再请求 analyze，防止闪烁
              }
              if (msg.status === 'done' && msg.id) {
                alert(msg.msg || '草稿已保存');
                // socket 没有 stats 时 fallback analyze
                fetch('/workshop/analyze', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                  },
                  body: JSON.stringify({ content: contentStr }),
                  credentials: 'include'
                }).then(async r => {
                  const ct = r.headers.get('content-type') || '';
                  if (ct.includes('text/html')) {
                    const html = await r.text();
                    alert('未登录或CSRF校验失败！\n' + html.slice(0, 200));
                    return {};
                  }
                  try {
                    return await r.json();
                  } catch (e) {
                    alert('响应不是JSON，可能后端异常！');
                    return {};
                  }
                }).then(res2 => {
                  if (res2.success && res2.stats) {
                    updateStats(res2.stats);
                  } else {
                    alert('分析失败：' + (res2.msg || '未知错误'));
                    updateStats({});
                  }
                }).catch(e => {
                  alert('分析请求异常：' + e);
                  updateStats({});
                });
              } else if (msg.status === 'processing') {
                // 可选：显示进度
              } else if (msg.status === 'error') {
                alert('保存失败：' + (msg.msg || '未知错误'));
              }
            };
            s.on('draft_status', s._workshopDraftStatusHandler);
          }
        }
      }
    });
  }

  if (mode === 'upload') {
    // 读取文件内容
    const file = form.file.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = function(e) {
        doSaveWithContent(e.target.result);
      };
      reader.readAsText(file);
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