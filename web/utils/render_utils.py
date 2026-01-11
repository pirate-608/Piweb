def render_content(raw, mode):
    if mode == 'markdown':
        import markdown2
        return markdown2.markdown(raw or '')
    return raw or ''
