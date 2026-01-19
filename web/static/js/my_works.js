// my_works.js - 我的作品列表页逻辑

document.addEventListener('DOMContentLoaded', function() {
  loadWorks(1);
});

function loadWorks(page) {
  fetch(`/workshop/api/my_works?page=${page}&per_page=10`, { credentials: 'include' })
    .then(r => r.json())
    .then(res => {
      if (!res.success) {
        document.getElementById('works-list').innerHTML = '<div class="alert alert-danger">加载失败：' + (res.msg || '未知错误') + '</div>';
        return;
      }
      renderWorks(res.data.works, res.data.page, res.data.per_page, res.data.total);
    });
}

function renderWorks(works, page, per_page, total) {
  const listDiv = document.getElementById('works-list');
  if (!works.length) {
    listDiv.innerHTML = '<div class="alert alert-info">暂无作品</div>';
    return;
  }
  let html = '<table class="table table-hover"><thead><tr><th>标题</th><th>更新时间</th><th>类型</th><th>协作</th><th>浏览</th><th>点赞</th><th>操作</th></tr></thead><tbody>';
  for (const w of works) {
    html += `<tr>
      <td>${escapeHtml(w.title)}</td>
      <td>${w.updated_at || ''}</td>
      <td>${w.pub_type || ''}</td>
      <td>${w.is_collab ? '是' : '否'}</td>
      <td>${w.views || 0}</td>
      <td>${w.likes || 0}</td>
      <td><a href="/workshop/re_editor/${w.id}" class="btn btn-sm btn-primary">编辑</a></td>
    </tr>`;
  }
  html += '</tbody></table>';
  listDiv.innerHTML = html;
  renderPagination(page, per_page, total);
}

function renderPagination(page, per_page, total) {
  const ul = document.getElementById('works-pagination');
  ul.innerHTML = '';
  const totalPages = Math.ceil(total / per_page);
  for (let i = 1; i <= totalPages; i++) {
    const li = document.createElement('li');
    li.className = 'page-item' + (i === page ? ' active' : '');
    const a = document.createElement('a');
    a.className = 'page-link';
    a.textContent = i;
    a.href = 'javascript:void(0)';
    a.onclick = () => loadWorks(i);
    li.appendChild(a);
    ul.appendChild(li);
  }
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, function(s) {
    return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'})[s];
  });
}
