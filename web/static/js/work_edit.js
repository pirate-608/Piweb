// work_edit.js - 作品编辑页逻辑（复用editor保存/分析范式，支持模式选择modal）

// socketio连接与推送机制 - 将原editor中的函数移到这里
var socket = null;
var joinedRoom = null;

function ensureSocketConnected() {
  if (!window.io) {
    console.error('Socket.IO library not loaded');
    return null;
  }
  
  if (socket && socket.connected) return socket;
  
  // 关闭旧的socket连接
  if (socket) {
    socket.disconnect();
    socket = null;
  }
  
  socket = io({
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
    forceNew: false,
    allowUpgrades: true,
    transportsOptions: {
      polling: { extraHeaders: { 'X-Requested-With': 'XMLHttpRequest' } }
    },
    maxHttpBufferSize: 10 * 1024 * 1024
  });
  
  // 基础事件监听
  socket.on('connect', () => {
    console.log('[work_edit] Socket connected, socket id:', socket.id);
    // 如果之前已加入房间，重新加入
    if (joinedRoom) {
      console.log('[work_edit] Rejoining room:', joinedRoom);
      socket.emit('join', { room: joinedRoom });
    }
  });
  
  socket.on('disconnect', (reason) => {
    console.log('[work_edit] Socket disconnected:', reason);
    // 尝试重新连接
    if (reason === 'io server disconnect' || reason === 'transport close') {
      setTimeout(() => {
        if (socket && !socket.connected) {
          console.log('[work_edit] Attempting to reconnect...');
          socket.connect();
        }
      }, 1000);
    }
  });
  
  socket.on('connect_error', (error) => {
    console.error('[work_edit] Socket connection error:', error);
  });
  
  socket.on('error', (error) => {
    console.error('[work_edit] Socket error:', error);
  });
  
  return socket;
}

// 统计信息更新函数 - 在顶部定义，确保所有地方都能访问
function updateStats(stats) {
  if (!stats) return;
  
  const statWords = document.getElementById('stat-words');
  const statCn = document.getElementById('stat-cn');
  const statEn = document.getElementById('stat-en');
  const statRich = document.getElementById('stat-rich');
  const statTop = document.getElementById('stat-top');
  const statSensitive = document.getElementById('stat-sensitive');
  const sectionList = document.getElementById('section-list');
  
  if (!statWords || !statCn || !statEn || !statRich || !statTop || !statSensitive || !sectionList) {
    console.warn('Some stat elements not found');
    return;
  }
  
  if (stats.words !== undefined) statWords.textContent = stats.words;
  if (stats.cn_chars !== undefined) statCn.textContent = stats.cn_chars;
  if (stats.en_words !== undefined) statEn.textContent = stats.en_words;
  if (stats.richness !== undefined) statRich.textContent = stats.richness;
  
  // 高频词渲染
  let topWordsArr = [];
  if (typeof stats.top_words === 'string') {
    try { topWordsArr = JSON.parse(stats.top_words); } catch (e) { topWordsArr = []; }
  } else if (Array.isArray(stats.top_words)) { topWordsArr = stats.top_words; }
  statTop.textContent = topWordsArr.length
    ? topWordsArr.map(w => `${w.word}(${w.freq ?? w.count ?? 0})`).join(', ')
    : '';
  
  // 敏感词渲染
  let sensitiveArr = [];
  if (typeof stats.sensitive_words === 'string') {
    try { sensitiveArr = JSON.parse(stats.sensitive_words); } catch (e) { sensitiveArr = []; }
  } else if (Array.isArray(stats.sensitive_words)) { sensitiveArr = stats.sensitive_words; }
  statSensitive.textContent = sensitiveArr.length
    ? sensitiveArr.map(w => (typeof w === 'string' ? w : w.word || '')).filter(Boolean).join(', ')
    : '';
  
  // 章节目录
  sectionList.innerHTML = '';
  if (Array.isArray(stats.sections)) {
    const normalSections = stats.sections.filter(sec => sec.title !== 'Introduction');
    let order = 1;
    normalSections.forEach(sec => {
      const li = document.createElement('li');
      let ratioStr = '';
      if (typeof sec.ratio === 'number') {
        ratioStr = '（占比 ' + (sec.ratio * 100).toFixed(1) + '%）';
      }
      li.textContent = (order++) + '. ' + (sec.title || '章节') + ratioStr;
      sectionList.appendChild(li);
    });
    
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

document.addEventListener('DOMContentLoaded', function() {
  console.log('[work_edit] DOM loaded, initializing...');
  
  // 页面加载即建立socket连接
  socket = ensureSocketConnected();
  
  // 检查是否获取到work-id元素
  const workIdElement = document.getElementById('work-id');
  if (!workIdElement) {
    console.error('Work ID element not found');
    document.getElementById('save-status').textContent = '页面初始化失败：找不到作品ID';
    return;
  }
  
  const workId = workIdElement.value;
  if (!workId) {
    console.error('Work ID is empty');
    document.getElementById('save-status').textContent = '页面初始化失败：作品ID为空';
    return;
  }
  
  console.log('[work_edit] Work ID:', workId);
  
  // 存储当前任务ID用于socket房间管理
  let currentTaskId = null;
  
  // 初始化socket事件监听（只注册一次）
  function initSocketListeners() {
    if (!socket) {
      console.warn('[work_edit] Socket not available for listeners');
      return;
    }
    
    // 移除旧的监听器避免重复
    socket.off('draft_status');
    // 添加新的监听器，只处理当前任务的推送
    socket.on('draft_status', function(msg) {
      console.log('[work_edit] 收到socketio draft_status推送：', msg);
      if (!msg || !msg.task_id || msg.task_id !== currentTaskId) {
        console.log('[work_edit] 忽略非当前任务推送', msg.task_id, currentTaskId);
        return;
      }
      if (msg.status === 'done') {
        updateStats(msg.stats || {});
        document.getElementById('save-status').textContent = '分析完成';
        enableAllButtons();
      } else if (msg.status === 'error') {
        document.getElementById('save-status').textContent = '分析失败: ' + (msg.error || '未知错误');
        enableAllButtons();
      } else if (msg.status === 'processing') {
        document.getElementById('save-status').textContent = '分析中...';
      }
    });
  }
  
  // 初始化socket监听
  initSocketListeners();
  
  // 辅助函数：启用所有按钮
  function enableAllButtons() {
    const saveDraftBtn = document.getElementById('save-draft-btn');
    const confirmSaveBtn = document.getElementById('confirmSaveBtn');
    if (saveDraftBtn) saveDraftBtn.disabled = false;
    if (confirmSaveBtn) confirmSaveBtn.disabled = false;
  }
  
  // 辅助函数：禁用所有按钮
  function disableAllButtons() {
    const saveDraftBtn = document.getElementById('save-draft-btn');
    const confirmSaveBtn = document.getElementById('confirmSaveBtn');
    if (saveDraftBtn) saveDraftBtn.disabled = true;
    if (confirmSaveBtn) confirmSaveBtn.disabled = true;
  }
  
  // 优先加载草稿，若无则加载正式内容
  function fillFormAndStats(data) {
    document.getElementById('title').value = data.title || '';
    document.getElementById('description').value = data.description || '';
    document.getElementById('content').value = data.content || '';
    if (data.stats) {
      console.log('[work_edit] 加载统计数据:', data.stats);
      updateStats(data.stats);
    }
  }

  function loadWorkOrDraft() {
    // 先拉取草稿
    fetch('/workshop/api/draft', {
      credentials: 'include',
      headers: { 'Accept': 'application/json' }
    })
      .then(r => r.json())
      .then(res => {
        if (res.success && res.data && Array.isArray(res.data.drafts)) {
          let drafts = res.data.drafts;
          let draft = drafts.find(d => String(d.work_id) === String(workId));
          if (!draft) {
            const title = document.getElementById('title')?.value;
            if (title) {
              draft = drafts.find(d => d.title === title);
            }
          }
          if (draft) {
            // 弹窗询问是否恢复草稿
            if (window.confirm('检测到有未发布草稿，是否恢复？\n选择“取消”将加载正式内容。')) {
              console.log('[work_edit] 用户选择恢复草稿:', draft);
              fillFormAndStats(draft);
              document.getElementById('save-status').textContent = '已恢复草稿';
              return;
            } else {
              console.log('[work_edit] 用户选择不恢复草稿，加载正式内容');
            }
          }
        }
        // 若无草稿或用户拒绝恢复，加载正式内容
        console.log('[work_edit] 未找到草稿或未恢复，加载正式内容...');
        fetch(`/workshop/api/work/${workId}`, { 
          credentials: 'include',
          headers: { 'Accept': 'application/json' }
        })
          .then(r => {
            if (!r.ok) {
              throw new Error(`HTTP error! status: ${r.status}`);
            }
            return r.json();
          })
          .then(res => {
            console.log('[work_edit] API response:', res);
            if (res.success && res.data) {
              fillFormAndStats(res.data);
              document.getElementById('save-status').textContent = '已加载正式内容';
              console.log('[work_edit] 作品数据加载完成');
            } else {
              const errorMsg = '加载失败：' + (res.msg || '未知错误');
              console.error('[work_edit]', errorMsg);
              document.getElementById('save-status').textContent = errorMsg;
            }
          })
          .catch(error => {
            console.error('[work_edit] 加载作品数据异常:', error);
            document.getElementById('save-status').textContent = '加载数据异常: ' + error.message;
          });
      })
      .catch(error => {
        console.error('[work_edit] 加载草稿异常:', error);
        document.getElementById('save-status').textContent = '加载草稿异常: ' + error.message;
      });
  }

  loadWorkOrDraft();
  
  // “保存草稿”按钮，仅保存为草稿，不触发审核/发布流程
  document.getElementById('save-draft-btn').addEventListener('click', function() {
    const saveDraftBtn = document.getElementById('save-draft-btn');
    saveDraftBtn.disabled = true;
    document.getElementById('save-status').textContent = '正在保存草稿...';
    
    const title = document.getElementById('title').value.trim();
    const description = document.getElementById('description').value.trim();
    const content = document.getElementById('content').value.trim();
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    let csrfToken = csrfInput ? csrfInput.value : '';
    csrfToken = csrfToken.replace(/^"|"$/g, '');
    
    if (!title || !content) {
      document.getElementById('save-status').textContent = '标题和正文不能为空';
      saveDraftBtn.disabled = false;
      return;
    }
    
    // 预生成task_id
    const tempTaskId = 'temp_' + Date.now() + '_' + Math.floor(Math.random() * 100000);
    currentTaskId = tempTaskId;
    const s = ensureSocketConnected();
    if (s) {
      // 离开旧房间
      if (joinedRoom && joinedRoom !== tempTaskId) {
        s.emit('leave', { room: joinedRoom });
      }
      joinedRoom = tempTaskId;
      s.emit('join', { room: joinedRoom });
      // 确保socket监听已注册
      initSocketListeners();
    }
    
    fetch(`/workshop/api/work/${workId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      credentials: 'include',
      body: JSON.stringify({
        id: workId,
        work_id: workId,
        title,
        description,
        content,
        pub_type: 'draft',
        client_task_id: tempTaskId
      })
    })
      .then(r => r.json())
      .then(res => {
        console.log('[work_edit] 草稿保存响应:', res);
        if (res.success) {
          document.getElementById('save-status').textContent = '草稿已保存';
          if (res.stats) {
            console.log('[work_edit] 草稿保存返回统计数据:', res.stats);
            updateStats(res.stats);
          }
          
          // 后端返回真实task_id后，更新房间（必须用真实 task_id，不能拼接 work_7_ 前缀）
          const realTaskId = (res.data && res.data.task_id) || res.task_id;
          if (s && realTaskId) {
            if (joinedRoom && joinedRoom !== realTaskId) {
              s.emit('leave', { room: joinedRoom });
            }
            currentTaskId = realTaskId;
            joinedRoom = realTaskId;
            s.emit('join', { room: realTaskId });
          }
          
          saveDraftBtn.disabled = false;
        } else {
          document.getElementById('save-status').textContent = '草稿保存失败：' + (res.msg || '未知错误');
          saveDraftBtn.disabled = false;
        }
      })
      .catch((error) => {
        console.error('[work_edit] 草稿保存异常:', error);
        document.getElementById('save-status').textContent = '草稿保存异常';
        saveDraftBtn.disabled = false;
      });
  });
  
  // modal取消按钮只用data-bs-dismiss，不手动hide，关闭后恢复confirmSaveBtn状态
  document.getElementById('saveModeModal').addEventListener('hidden.bs.modal', function() {
    enableAllButtons();
  });
  
  // modal确认保存
  document.getElementById('confirmSaveBtn').addEventListener('click', function() {
    disableAllButtons();
    document.getElementById('save-status').textContent = '内容分析中...';
    
    const pubType = document.querySelector('input[name="saveMode"]:checked').value;
    const title = document.getElementById('title').value.trim();
    const description = document.getElementById('description').value.trim();
    const content = document.getElementById('content').value.trim();
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    let csrfToken = csrfInput ? csrfInput.value : '';
    csrfToken = csrfToken.replace(/^"|"$/g, '');
    
    if (!title || !content) {
      document.getElementById('save-status').textContent = '标题和正文不能为空';
      enableAllButtons();
      return;
    }
    
    // 先分析内容
    fetch('/workshop/analyze', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      credentials: 'include',
      body: JSON.stringify({ content })
    })
      .then(r => r.json())
      .then(res => {
        console.log('[work_edit] 内容分析响应:', res);
        if (!res.success) {
          document.getElementById('save-status').textContent = '内容审核未通过：' + (res.msg || '未知错误');
          enableAllButtons();
          return;
        }
        
        // 审核通过，自动刷新统计区和章节目录
        updateStats(res.stats || {});
        let statMsg = '内容分析通过';
        if (res.stats && res.stats.words) statMsg += `，字数：${res.stats.words}`;
        if (res.stats && res.stats.richness) statMsg += `，丰富度：${res.stats.richness}`;
        if (res.stats && res.stats.sensitive_words && res.stats.sensitive_words.length) statMsg += `，敏感词：${res.stats.sensitive_words.join(',')}`;
        document.getElementById('save-status').textContent = statMsg;
        
        // 继续保存
        fetch(`/workshop/api/work/${workId}`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          credentials: 'include',
          body: JSON.stringify({
            id: workId,
            title,
            description,
            content,
            pub_type: pubType
          })
        })
          .then(r => r.json())
          .then(res2 => {
            console.log('[work_edit] 发布保存响应:', res2);
            if (res2.success) {
              document.getElementById('save-status').textContent = '发布成功';
              const modal = bootstrap.Modal.getInstance(document.getElementById('saveModeModal'));
              if (modal) modal.hide();
              // 跳转到作品详情页
              let workId = (res2.data && res2.data.work_id) || res2.work_id || window.workId;
              if (workId) {
                setTimeout(function() {
                  window.location.href = '/workshop/work/' + workId;
                }, 600);
              }
            } else {
              document.getElementById('save-status').textContent = '发布失败：' + (res2.msg || '未知错误');
            }
            enableAllButtons();
          })
          .catch((error) => {
            console.error('[work_edit] 保存异常:', error);
            document.getElementById('save-status').textContent = '保存异常';
            enableAllButtons();
          });
      })
      .catch((error) => {
        console.error('[work_edit] 内容分析异常:', error);
        document.getElementById('save-status').textContent = '内容分析异常';
        enableAllButtons();
      });
  });
  
  // 为发布按钮添加事件监听（如果存在）
  const publishBtn = document.getElementById('publish-btn');
  if (publishBtn) {
    publishBtn.addEventListener('click', function() {
      console.log('[work_edit] 发布按钮点击');
    });
  }
  
  console.log('[work_edit] 初始化完成');
});