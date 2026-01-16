from flask_dropzone import Dropzone

def init_uploads(app):
    # 仅配置Dropzone，上传逻辑由各蓝图自定义实现
    app.config['DROPZONE_UPLOAD_MULTIPLE'] = True
    app.config['DROPZONE_ALLOWED_FILE_CUSTOM'] = True
    app.config['DROPZONE_ALLOWED_FILE_TYPE'] = 'image/*, .pdf, .docx, .txt, .md'
    app.config['DROPZONE_MAX_FILE_SIZE'] = 10  # MB
    app.config['DROPZONE_MAX_FILES'] = 10
    dropzone = Dropzone(app)
    return dropzone
