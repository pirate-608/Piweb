// coeditor.js - 协作编辑核心逻辑
// 依赖：页面URL为 /workshop/coeditor/<work_id>
// 主要流程：页面加载自动加锁，加载内容，编辑后提交，离开时自动解锁

(function() {
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
        if (res.success) {
          /* 草稿保存成功弹窗，仅调试用 */
          alert('草稿保存成功！（仅调试用）');
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

  // 初始化
  lockAndLoad();
})();
