// workshop_editor.js - 工坊创作页面交互
// 依赖：页面需通过<script src="/static/js/socket.io.min.js"></script>引入socket.io客户端
// 优化：页面加载即建立socket.io连接，保存草稿后join房间，支持断线重连

// 全局变量
let socket = null;
let joinedRoom = null;

// ========== 统计信息更新函数 ==========

function updateStats(stats) {
  const statWords = document.getElementById('stat-words');
  const statCn = document.getElementById('stat-cn');
  const statEn = document.getElementById('stat-en');
  const statRich = document.getElementById('stat-rich');
  const statTop = document.getElementById('stat-top');
  const statSensitive = document.getElementById('stat-sensitive');
  const sectionList = document.getElementById('section-list');
  
  if (!statWords || !statCn || !statEn || !statRich || !statTop || !statSensitive || !sectionList) {
    console.warn('[workshop_editor] Some stat elements not found');
    return;
  }
  
  statWords.textContent = stats.words || 0;
  statCn.textContent = stats.cn_chars || 0;
  statEn.textContent = stats.en_words || 0;
  statRich.textContent = stats.richness || 0;
  
  // 高频词渲染
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
  statTop.textContent = topWordsArr.length
    ? topWordsArr.map(w => `${w.word}(${w.freq ?? w.count ?? 0})`).join(', ')
    : '';
  
  // 敏感词渲染
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
  statSensitive.textContent = sensitiveArr.length
    ? sensitiveArr.map(w => (typeof w === 'string' ? w : w.word || '')).filter(Boolean).join(', ')
    : '';
  
  // 章节目录
  sectionList.innerHTML = '';
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

// ========== Socket.IO 连接管理 ==========

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

// ========== 自动加载最近草稿 ==========

window.addEventListener('DOMContentLoaded', function() {
  console.log('[workshop_editor] DOMContentLoaded fired, 自动加载草稿逻辑开始');
  
  // 绑定创作方式切换事件
  document.querySelectorAll('input[name="mode"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
      const mode = this.value;
      const onlineEditor = document.getElementById('online-editor');
      const uploadArea = document.getElementById('upload-area');
      if (mode === 'upload') {
        if (onlineEditor) onlineEditor.classList.add('d-none');
        if (uploadArea) uploadArea.classList.remove('d-none');
      } else {
        if (onlineEditor) onlineEditor.classList.remove('d-none');
        if (uploadArea) uploadArea.classList.add('d-none');
      }
    });
  });
  
  // 只在初次加载时自动填充
  const form = document.getElementById('workshop-form');
  let workId = '';
  if (form && form.work_id) {
    workId = form.work_id.value;
  } else {
    // 兼容hidden input[name=work_id]
    const workIdInput = document.querySelector('input[name="work_id"]');
    if (workIdInput) workId = workIdInput.value;
  }
  let draftApiUrl = '/workshop/api/draft';
  if (workId) {
    draftApiUrl += `?work_id=${encodeURIComponent(workId)}`;
  }
  fetch(draftApiUrl, {
    method: 'GET',
    credentials: 'include'
  })
  .then(r => {
    console.log('[workshop_editor] /workshop/api/draft fetch响应', r);
    return r.json();
  })
  .then(res => {
    console.log('[workshop_editor] /workshop/api/draft 响应内容', res);
    const drafts = res.data && res.data.drafts;
    if (res && res.data && res.data.drafts) {
      console.log('[workshop_editor] drafts 列表', res.data.drafts);
    } else {
      console.warn('[workshop_editor] drafts 列表为空或结构异常', res);
    }
    if (res.success && drafts && drafts.length > 0) {
      // 取最近一条
      const draft = drafts[0];
      // 弹窗询问是否恢复草稿
      if (window.confirm('检测到有未发布草稿，是否恢复？\n选择“取消”将不恢复。')) {
        let draftDetailUrl = `/workshop/api/draft?id=${draft.id}`;
        if (workId) draftDetailUrl += `&work_id=${encodeURIComponent(workId)}`;
        fetch(draftDetailUrl, {
          method: 'GET',
          credentials: 'include'
        })
        .then(r2 => {
          console.log('[workshop_editor] /workshop/draft/<id> fetch响应', r2);
          return r2.json();
        })
        .then(res2 => {
          console.log('[workshop_editor] /workshop/draft/<id> 响应内容', res2);
          // 兼容后端返回 draft、data.draft、data 直接为草稿对象，或 data.drafts 为数组
          let draftData = null;
          const draftId = draft.id;
          if (res2.draft) {
            draftData = res2.draft;
          } else if (res2.data && res2.data.draft) {
            draftData = res2.data.draft;
          } else if (res2.data && Array.isArray(res2.data.drafts)) {
            draftData = res2.data.drafts.find(d => String(d.id) === String(draftId)) || res2.data.drafts[0];
          } else if (res2.data && typeof res2.data === 'object' && Object.keys(res2.data).length > 0) {
            draftData = res2.data;
          }
          if (res2.success && draftData) {
            console.log('[workshop_editor] draftData 详情', draftData);
            // 打印表单赋值前的状态
            const form = document.getElementById('workshop-form');
            console.log('[workshop_editor] 填充表单前', {
              title: form.title?.value,
              description: form.description?.value,
              content: form.content?.value,
              mode: form.mode?.value
            });
            // 填充表单
            form.title.value = draftData.title || '';
            form.description.value = draftData.description || '';
            form.content.value = draftData.content || '';
            // 设置创作方式
            form.mode.value = draftData.type === 'upload' ? 'upload' : 'online';
            // 触发radio change事件，确保UI切换
            const modeRadio = document.querySelector('input[name="mode"]:checked');
            if (modeRadio) modeRadio.dispatchEvent(new Event('change', {bubbles:true}));
            // 主动触发input事件，确保富文本/校验/发布按钮等联动
            ['title','description','content'].forEach(function(name){
              const el = form[name];
              if (el) {
                el.dispatchEvent(new Event('input', {bubbles:true}));
              }
            });
            // 打印表单赋值后的状态
            setTimeout(() => {
              console.log('[workshop_editor] 填充表单后', {
                title: form.title?.value,
                description: form.description?.value,
                content: form.content?.value,
                mode: form.mode?.value
              });
            }, 100);
            // 自动还原统计信息（如有）
            if (draftData.stats) {
              console.log('[workshop_editor] 自动还原统计信息', draftData.stats);
              if (typeof updateStats === 'function') updateStats(draftData.stats);
            }
            // 如有全局发布按钮校验函数，自动触发
            if (window.checkPublishEnable) window.checkPublishEnable();
          } else {
            console.warn('[workshop_editor] draftData 为空或结构异常', res2);
          }
        });
      } else {
        console.log('[workshop_editor] 用户选择不恢复草稿，不填充');
      }
    }
  });
  
  console.log('[workshop_editor] 自动加载草稿逻辑结束');
  // 监听 input/radio 事件
  document.querySelectorAll('input, textarea').forEach(el => {
    el.addEventListener('input', function (e) {
      console.log('[workshop_editor] input 事件', {
        name: e.target.name,
        value: e.target.value,
        id: e.target.id
      });
      // ...existing code...
    });
  });
  document.querySelectorAll('input[type="radio"]').forEach(el => {
    el.addEventListener('change', function (e) {
      console.log('[workshop_editor] radio change 事件', {
        name: e.target.name,
        value: e.target.value,
        id: e.target.id
      });
      // ...existing code...
    });
  });
  
  // 禁止标题栏回车触发表单提交，避免跳转错误页面
  document.getElementById('title').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      this.blur();
    }
  });
});

// ========== 保存草稿函数 ==========

function saveDraftWithSocketReady(form, callback) {
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
    // 恢复按钮状态，避免卡死
    const saveBtn = document.getElementById('save-btn');
    saveBtn.disabled = false;
    saveBtn.innerText = '保存草稿';
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
    // 提取work_id
    let workId = '';
    if (form.work_id) {
      workId = form.work_id.value;
    } else {
      const workIdInput = document.querySelector('input[name="work_id"]');
      if (workIdInput) workId = workIdInput.value;
    }
    if (workId) {
      data.work_id = workId;
    }
    
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    let csrfToken = csrfInput ? csrfInput.value : '';
    csrfToken = csrfToken.replace(/^"|"$/g, '');
    console.log('CSRF Token:', csrfToken);
    
    fetch('/workshop/api/draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(data),
      credentials: 'include'
    })
    .then(async r => {
      console.log('[save-btn] 保存草稿请求已返回，处理响应...');
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('text/html')) {
        const html = await r.text();
        alert('未登录或CSRF校验失败！\n' + html.slice(0, 200));
        // 兜底恢复按钮
        const saveBtn = document.getElementById('save-btn');
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
        if (typeof callback === 'function') callback(false);
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
        if (typeof callback === 'function') callback(false);
        return {};
      }
    })
    .then(res => {
      console.log('[save-btn] 保存草稿响应：', res);
      // fetch成功后立即恢复按钮，无论socketio消息如何
      const saveBtn = document.getElementById('save-btn');
      saveBtn.disabled = false;
      saveBtn.innerText = '保存草稿';
      
      // 兼容后端返回结构（data.task_id/draft_id）
      let taskId = null, draftId = null;
      if (res && res.data) {
        taskId = res.data.task_id;
        draftId = res.data.draft_id;
      } else {
        // 兼容旧结构
        taskId = res.task_id;
        draftId = res.draft_id || res.id;
      }
      
      console.log('[debug] res.success:', res.success, 'taskId:', taskId, 'draftId:', draftId, 'res:', res);
      const s = ensureSocketConnected();
      console.log('[debug] ensureSocketConnected()返回:', s);
      console.log('[debug] 当前joinedRoom:', joinedRoom);
      
      if (res.success && taskId) {
        // 保存草稿成功时写入 form.dataset.draftId
        if (draftId) form.dataset.draftId = draftId;
        if (typeof callback === 'function') callback(true, draftId);
        
        // 恢复socketio房间和推送监听（用于后续统计等）
        if (s) {
          joinedRoom = taskId;
          console.log('[save-btn] join房间', taskId);
          s.emit('join', { room: taskId });
          console.log('[debug] 已执行 s.emit("join", { room })');
          
          if (!s._workshopDraftStatusHandler) {
            console.log('[save-btn] 注册socketio draft_status事件监听');
            s._workshopDraftStatusHandler = function(msg) {
              console.log('[save-btn] 收到socketio draft_status推送：', msg);
              if (msg.status === 'done') {
                updateStats(msg.stats || {});
                // 新增：保存成功时写入draftId并刷新发布按钮
                if (msg.id) {
                  const form = document.getElementById('workshop-form');
                  form.dataset.draftId = msg.id;
                  if (window.checkPublishEnable) window.checkPublishEnable();
                }
                return;
              }
              if (msg.status === 'error') {
                updateStats(msg.stats || {});
                return;
              }
              if (msg.status === 'processing') {
                // 可选：显示进度
              }
            };
            s.on('draft_status', s._workshopDraftStatusHandler);
            console.log('[debug] 已注册 s.on("draft_status", handler)');
          }
        } else {
          console.warn('[debug] socketio连接对象s不存在，无法join房间和注册监听');
        }
      } else {
        console.warn('[debug] res.success/taskId条件不满足，未执行join/监听逻辑');
        if (typeof callback === 'function') callback(false);
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
            doSaveWithContent(res.content, callback);
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
    doSaveWithContent(form.content.value, callback);
  }
}

// ========== 保存按钮点击事件 ==========

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
    saveDraftWithSocketReady(form, (success, draftId) => {
      if (success && draftId) {
        const s = ensureSocketConnected();
        // draftId仅用于前端标识，房间仍用taskId（由saveDraftWithSocketReady内部处理）
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
    });
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

// ========== 页面初始化 ==========

// 页面加载即建立socket连接
ensureSocketConnected();