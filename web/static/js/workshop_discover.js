// workshop_discover.js

document.addEventListener('DOMContentLoaded', function () {
  const worksGrid = document.getElementById('worksGrid');
  const pagination = document.getElementById('pagination');
  const searchForm = document.getElementById('searchForm');
  const worksTab = document.getElementById('worksTab');

  let currentPage = 1;
  let currentSort = 'latest'; // 仅支持'latest'和'hot'

  let isLoading = false;
  let hasMore = true;
  let lastQuery = '';

  function showSkeleton(show = true) {
    const skeleton = document.getElementById('skeletonLoader');
    if (!skeleton) return;
    if (show) {
      skeleton.style.display = '';
      worksGrid.style.display = 'none';
    } else {
      skeleton.style.display = 'none';
      worksGrid.style.display = '';
    }
  }

  function fetchWorks(page = 1, append = false) {
    if (isLoading) return;
    isLoading = true;
    showSkeleton(true);
    const formData = new FormData(searchForm);
    const params = new URLSearchParams();
    for (const [k, v] of formData.entries()) {
      if (v) params.append(k, v);
    }
    params.set('page', page);
    params.set('sort', currentSort);
    lastQuery = params.toString();
    fetch(`/workshop/api/works?${lastQuery}`)
      .then(res => res.json())
      .then(data => {
        if (append) {
          appendWorks(data.works);
        } else {
          renderWorks(data.works);
        }
        renderPagination(data.page, Math.ceil(data.total / data.per_page));
        hasMore = data.page * data.per_page < data.total;
        isLoading = false;
        showSkeleton(false);
      })
      .catch(() => { isLoading = false; showSkeleton(false); });
  }

  function appendWorks(works) {
    if (!works.length) return;
    for (const w of works) {
      // ...existing code...
      const card = document.createElement('div');
      card.className = 'col';
      card.innerHTML = `
        <div class="card h-100 shadow rounded-4 border-0 position-relative work-card">
          <div class="theme-bar" style="height:6px;background:${themeColor(w.theme)};border-radius:12px 12px 0 0;"></div>
          <div class="card-body pb-2">
            <div class="d-flex align-items-center mb-2">
              <div class="avatar-circle me-2" title="${escapeHtml(w.author)}">
                ${authorAvatar(w.author)}
              </div>
              <h5 class="card-title mb-0 flex-grow-1 text-truncate" title="${escapeHtml(w.title)}">${escapeHtml(w.title)}
                ${w.is_collab ? '<span class="badge bg-info ms-2">协作</span>' : ''}
              </h5>
              <span class="badge bg-secondary ms-2">${escapeHtml(w.theme || '无主题')}</span>
            </div>
            <div class="card-subtitle mb-2 text-muted small">
              <span title="作者">${escapeHtml(w.author)}</span> · <span title="发布时间">${escapeHtml(w.created_at)}</span>
            </div>
            <p class="card-text text-truncate work-desc" title="${escapeHtml(w.description || '')}">
              ${escapeHtml(w.description || '').slice(0, 60)}${w.description && w.description.length > 60 ? '...' : ''}
            </p>
            <div class="mb-2 work-keywords">
              ${renderKeywords(w.keywords)}
            </div>
          </div>
          <div class="card-footer d-flex justify-content-between align-items-center small bg-white border-0 rounded-bottom-4">
            <span>
              <i class="bi bi-eye text-primary"></i> <span class="me-2">${w.views}</span>
              <i class="bi bi-heart text-danger" style="cursor:default;"></i> <span class="work-likes" data-id="${w.id}">${w.likes}</span>
            </span>
            <a href="/workshop/work/${w.id}" class="stretched-link">详情</a>
          </div>
        </div>
      `;
      worksGrid.appendChild(card);
      // 卡片区点赞仅显示，不可点击
    }
  }

  function renderWorks(works) {
    worksGrid.innerHTML = '';
    if (!works.length) {
      worksGrid.innerHTML = '<div class="col"><div class="alert alert-warning">暂无作品</div></div>';
      return;
    }
    for (const w of works) {
      // ...existing code...
      const card = document.createElement('div');
      card.className = 'col';
      card.innerHTML = `
        <div class="card h-100 shadow rounded-4 border-0 position-relative work-card">
          <div class="theme-bar" style="height:6px;background:${themeColor(w.theme)};border-radius:12px 12px 0 0;"></div>
          <div class="card-body pb-2">
            <div class="d-flex align-items-center mb-2">
              <div class="avatar-circle me-2" title="${escapeHtml(w.author)}">
                ${authorAvatar(w.author)}
              </div>
              <h5 class="card-title mb-0 flex-grow-1 text-truncate" title="${escapeHtml(w.title)}">${escapeHtml(w.title)}
                ${w.is_collab ? '<span class="badge bg-info ms-2">协作</span>' : ''}
              </h5>
              <span class="badge bg-secondary ms-2">${escapeHtml(w.theme || '无主题')}</span>
            </div>
            <div class="card-subtitle mb-2 text-muted small">
              <span title="作者">${escapeHtml(w.author)}</span> · <span title="发布时间">${escapeHtml(w.created_at)}</span>
            </div>
            <p class="card-text text-truncate work-desc" title="${escapeHtml(w.description || '')}">
              ${escapeHtml(w.description || '').slice(0, 60)}${w.description && w.description.length > 60 ? '...' : ''}
            </p>
            <div class="mb-2 work-keywords">
              ${renderKeywords(w.keywords)}
            </div>
          </div>
          <div class="card-footer d-flex justify-content-between align-items-center small bg-white border-0 rounded-bottom-4">
            <span>
              <i class="bi bi-eye text-primary"></i> <span class="me-2">${w.views}</span>
              <i class="bi bi-heart text-danger" style="cursor:default;"></i> <span>${w.likes}</span>
            </span>
            <a href="/workshop/work/${w.id}" class="stretched-link">详情</a>
          </div>
        </div>
      `;
      worksGrid.appendChild(card);
      // 点赞按钮事件绑定
      card.querySelectorAll('.work-like-btn').forEach(function(btn){
        btn.onclick = function(e){
          e.stopPropagation();
          const workId = btn.getAttribute('data-id');
          fetch(`/workshop/api/like`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ work_id: workId }),
            credentials: 'include'
          })
          .then(r => r.json())
          .then(res => {
            if(res.success && typeof res.likes === 'number'){
              const likesSpan = card.querySelector('.work-likes[data-id="'+workId+'"]');
              if(likesSpan) likesSpan.textContent = res.likes;
              btn.classList.add('bi-heart-fill');
              btn.classList.remove('bi-heart');
            }else{
              alert(res.msg || '点赞失败');
            }
          })
          .catch(()=>{ alert('网络异常，点赞失败'); });
        };
      });
    }
  }

    function renderKeywords(keywords) {
      if (!keywords) return '';
      return keywords.split(',').map(k => `<span class="badge bg-light text-dark border me-1 work-keyword" title="${escapeHtml(k)}">${escapeHtml(k)}</span>`).join('');
    }

    function themeColor(theme) {
      // 可根据主题自定义色彩
      switch (theme) {
        case '社会': return '#4e73df';
        case '科技': return '#1cc88a';
        case '文学': return '#f6c23e';
        default: return '#e3e6f0';
      }
    }

    function authorAvatar(author) {
      if (!author) return '<span class="avatar-initial">?</span>';
      const initial = author.trim()[0] || '?';
      return `<span class="avatar-initial">${escapeHtml(initial)}</span>`;
    }

  function renderPagination(page, totalPages) {
    pagination.innerHTML = '';
    if (totalPages <= 1) return;
    for (let i = 1; i <= totalPages; i++) {
      const li = document.createElement('li');
      li.className = 'page-item' + (i === page ? ' active' : '');
      li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
      li.addEventListener('click', e => {
        e.preventDefault();
        currentPage = i;
        fetchWorks(currentPage);
      });
      pagination.appendChild(li);
    }
  }

  // Tab切换
  worksTab.querySelectorAll('.nav-link').forEach(tab => {
    tab.addEventListener('click', function (e) {
      e.preventDefault();
      worksTab.querySelectorAll('.nav-link').forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      // 只允许latest/hot
      if (this.dataset.sort === 'latest' || this.dataset.sort === 'hot') {
        currentSort = this.dataset.sort;
        currentPage = 1;
        fetchWorks(currentPage);
      }
    });
  });

  // 搜索表单
  searchForm.addEventListener('submit', function (e) {
    e.preventDefault();
    currentPage = 1;
    fetchWorks(currentPage);
  });

  // HTML转义
  function escapeHtml(str) {
    return String(str).replace(/[&<>"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  // 卡片悬停显示完整简介
  worksGrid.addEventListener('mouseover', function(e) {
    const desc = e.target.closest('.work-desc');
    if (desc) desc.classList.remove('text-truncate');
  });
  worksGrid.addEventListener('mouseout', function(e) {
    const desc = e.target.closest('.work-desc');
    if (desc) desc.classList.add('text-truncate');
  });

  // 关键词悬停高亮
  worksGrid.addEventListener('mouseover', function(e) {
    if (e.target.classList.contains('work-keyword')) {
      e.target.classList.add('bg-warning','text-dark');
    }
  });
  worksGrid.addEventListener('mouseout', function(e) {
    if (e.target.classList.contains('work-keyword')) {
      e.target.classList.remove('bg-warning','text-dark');
    }
  });

  // 懒加载/无限滚动
  window.addEventListener('scroll', function () {
    if (!hasMore || isLoading) return;
    const scrollY = window.scrollY || window.pageYOffset;
    const viewport = window.innerHeight;
    const fullHeight = document.body.scrollHeight;
    if (scrollY + viewport > fullHeight - 200) {
      currentPage++;
      fetchWorks(currentPage, true);
    }
  });

  // 首次加载
  fetchWorks(currentPage);
});
