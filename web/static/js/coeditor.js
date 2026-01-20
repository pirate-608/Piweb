// coeditor.js - 协作编辑核心逻辑
// 依赖：页面URL为 /workshop/coeditor/<work_id>
// 主要流程：页面加载自动加锁，加载内容，编辑后提交，离开时自动解锁

// ========== 统计信息渲染函数 ==========
function updateStats(stats) {
  const statWords = document.getElementById('stat-words');
  const statCn = document.getElementById('stat-cn');
  const statEn = document.getElementById('stat-en');
  const statRich = document.getElementById('stat-rich');
  const statTop = document.getElementById('stat-top');
  const statSensitive = document.getElementById('stat-sensitive');
  const sectionList = document.getElementById('section-list');

  if (!statWords || !statCn || !statEn || !statRich || !statTop || !statSensitive || !sectionList) {
    console.warn('[coeditor] Some stat elements not found');
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

  // 章节目录渲染
  sectionList.innerHTML = '';
  console.log('[coeditor] 接口返回sections:', stats.sections);
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

(function() {
    // ========== Socket.IO 连接管理 ========== 
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
      });
      socket.on('disconnect', (reason) => {
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
      socket.on('error', (err) => {
        console.error('Socket error:', err);
      });
      // draft_status 事件监听全局绑定一次
      socket.on('draft_status', function(msg) {
        console.log('[coeditor] 收到 draft_status:', msg);
        console.log('[coeditor] draft_status 字段:', {
          status: msg.status,
          stats: msg.stats,
          msg: msg.msg
        });
        if (msg.status === 'done') {
          if (msg.stats) {
            console.log('[coeditor] draft_status stats:', msg.stats);
            if (typeof updateStats === 'function') updateStats(msg.stats);
          } else {
            alert('草稿保存成功，但未收到统计信息！');
            console.warn('[coeditor] draft_status stats 字段为空或异常:', msg);
          }
          // alert('草稿保存并分析完成！'); // 已注释，避免弹窗干扰
          return;
        }
        if (msg.status === 'error') {
          alert('草稿保存失败：' + (msg.msg || '未知错误'));
          return;
        }
        if (msg.status === 'processing') {
          // 可选：显示进度
        }
      });
      return socket;
    }
  // 获取作品ID
  function getWorkId() {
    const match = window.location.pathname.match(/coeditor\/(\d+)/);
    return match ? match[1] : null;
  }
  const workId = getWorkId();
  if (!workId) {
    alert('未获取到作品ID，无法编辑');
    return;
  }
  const form = document.getElementById('coeditor-form');
  const submitBtn = document.getElementById('submit-btn');
  const modal = new bootstrap.Modal(document.getElementById('publishModal'));
  const modalSubmitBtn = document.getElementById('modal-submit-btn');

  // 保存草稿按钮逻辑
  const saveBtn = document.getElementById('save-btn');
  saveBtn.onclick = function() {
    saveBtn.disabled = true;
    saveBtn.innerText = '保存中...';
    const data = {
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      content: form.content.value.trim()
    };
    if (!data.title || !data.content) {
      alert('标题和正文不能为空');
      saveBtn.disabled = false;
      saveBtn.innerText = '保存草稿';
      return;
    }
    fetch(`/workshop/api/draft`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': form.csrf_token.value
      },
      body: JSON.stringify({ ...data, work_id: workId }),
      credentials: 'include'
    })
      .then(r => r.json())
      .then(res => {
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
        if (res.success && res.data && res.data.task_id) {
          // 建立socket连接并join房间
          const s = ensureSocketConnected();
          joinedRoom = res.data.task_id;
          s.emit('join', { room: joinedRoom });
        } else if (res.success) {
          alert('草稿保存成功！（无推送）');
        } else {
          alert(res.msg || '草稿保存失败');
        }
      })
      .catch(() => {
        saveBtn.disabled = false;
        saveBtn.innerText = '保存草稿';
        alert('网络异常，草稿保存失败');
      });
  };

  // 自动加锁
  function lockAndLoad() {
    fetch(`/workshop/api/works/${workId}/lock`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'X-CSRFToken': form.csrf_token.value
      }
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          loadContent();
        } else {
          alert(res.msg || '加锁失败，无法编辑');
          window.history.back();
        }
      })
      .catch(() => {
        alert('网络异常，无法加锁');
        window.history.back();
      });
  }

  // 加载原内容
  function loadContent() {
    // 优先加载草稿
    fetch(`/workshop/api/draft?work_id=${workId}`, {
      method: 'GET',
      credentials: 'include'
    })
      .then(r => r.json())
      .then(res => {
        console.log('[coeditor] 草稿接口返回:', res);
        let draft = null;
        if (res.success) {
          if (res.draft) {
            draft = res.draft;
          } else if (res.data && res.data.draft) {
            draft = res.data.draft;
          } else if (res.data && Array.isArray(res.data.drafts) && res.data.drafts.length > 0) {
            draft = res.data.drafts[0];
          }
        }
        if (draft) {
          form.title.value = draft.title || '';
          form.description.value = draft.description || '';
          form.content.value = draft.content || '';
          console.log('[coeditor] 已加载草稿:', draft);
        } else {
          // 无草稿则加载正式内容
          fetch(`/workshop/api/work/${workId}`)
            .then(r2 => r2.json())
            .then(res2 => {
              console.log('[coeditor] 正式内容接口返回:', res2);
              let work = null;
              if (res2.success) {
                if (res2.work) {
                  work = res2.work;
                } else if (res2.data && res2.data.work) {
                  work = res2.data.work;
                } else if (res2.data && typeof res2.data === 'object' && Object.keys(res2.data).length > 0) {
                  work = res2.data;
                }
              }
              if (work) {
                form.title.value = work.title || '';
                form.description.value = work.description || '';
                form.content.value = work.content || '';
                console.log('[coeditor] 已加载正式内容:', work);
              } else {
                alert((res2 && (res2.msg || res2.message)) || '加载作品内容失败');
                console.error('[coeditor] 加载作品内容失败，返回内容:', res2);
                window.history.back();
              }
            })
            .catch(err => {
              alert('加载作品内容异常: ' + err);
              console.error('[coeditor] 加载作品内容异常:', err);
              window.history.back();
            });
        }
      })
      .catch(err => {
        alert('加载草稿异常: ' + err);
        console.error('[coeditor] 加载草稿异常:', err);
        window.history.back();
      });
  }

  // 提交编辑，弹出实名/匿名modal
  submitBtn.onclick = function() {
    modal.show();
  };

  // modal内提交
  modalSubmitBtn.onclick = function() {
    const isAnonymous = document.getElementById('anonymous').checked;
    const agree = document.getElementById('agree-protocol').checked;
    if (!agree) {
      alert('请同意平台作品发布协议');
      return;
    }
    const data = {
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      content: form.content.value.trim(),
      is_anonymous: isAnonymous ? 1 : 0,
      agree_protocol: agree
    };
    if (!data.title || !data.content) {
      alert('标题和正文不能为空');
      return;
    }
    modalSubmitBtn.disabled = true;
    fetch(`/workshop/api/works/${workId}/edit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': form.csrf_token.value
      },
      body: JSON.stringify(data),
      credentials: 'include'
    })
      .then(r => r.json())
      .then(res => {
        modalSubmitBtn.disabled = false;
        if (res.success) {
          alert('编辑提交成功！');
          unlockAndBack();
        } else {
          alert(res.msg || '提交失败');
        }
      })
      .catch(() => {
        modalSubmitBtn.disabled = false;
        alert('网络异常，提交失败');
      });
  };

  // 离开页面自动解锁
  function unlockAndBack() {
    fetch(`/workshop/api/works/${workId}/unlock`, {method: 'POST', credentials: 'include'})
      .then(() => {
        window.location.href = `/workshop/work/${workId}`;
      });
  }
  window.addEventListener('beforeunload', function() {
    navigator.sendBeacon(`/workshop/api/works/${workId}/unlock`);
  });

  // 禁止标题栏回车触发表单提交，避免跳转错误页面
  document.getElementById('title').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      // 可选：可在此处实现标题多行支持或直接失焦
      this.blur();
    }
  });

  // 初始化
  // 页面加载即建立socket连接
  ensureSocketConnected();
  lockAndLoad();
})();
