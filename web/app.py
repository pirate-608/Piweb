import os
import ctypes
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.after_request
def add_header(response):
    # 尝试解决 ngrok 免费版拦截页面问题 (主要针对 API 调用或特定客户端)
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL_PATH = os.path.join(BASE_DIR, 'build', 'libgrading.dll')
DATA_FILE = os.path.join(BASE_DIR, 'questions.txt')

# Load C Library
try:
    lib = ctypes.CDLL(DLL_PATH)
    # int calculate_score(const char* user_ans, const char* correct_ans, int full_score);
    lib.calculate_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    lib.calculate_score.restype = ctypes.c_int
    print(f"Successfully loaded DLL from {DLL_PATH}")
except Exception as e:
    print(f"Error loading DLL: {e}")
    lib = None

def load_questions():
    questions = []
    if not os.path.exists(DATA_FILE):
        return questions
    
    try:
        with open(DATA_FILE, 'r', encoding='gbk') as f: # Assuming GBK for Windows compatibility with C app usually
             for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split('|')
                if len(parts) >= 3:
                    questions.append({
                        'content': parts[0],
                        'answer': parts[1],
                        'score': int(parts[2])
                    })
    except UnicodeDecodeError:
        # Try UTF-8 if GBK fails
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
             for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split('|')
                if len(parts) >= 3:
                    questions.append({
                        'content': parts[0],
                        'answer': parts[1],
                        'score': int(parts[2])
                    })
    return questions

def save_question(content, answer, score):
    # Append with newline
    with open(DATA_FILE, 'a', encoding='gbk') as f: # Use GBK to match C app likely behavior on Windows
        f.write(f"\n{content}|{answer}|{score}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/exam', methods=['GET', 'POST'])
def exam():
    questions = load_questions()
    if request.method == 'POST':
        total_score = 0
        results = []
        
        for i, q in enumerate(questions):
            user_ans = request.form.get(f'q_{i}', '')
            
            # Use C function for grading if available
            if lib:
                # Encode strings to bytes for C (GBK for Windows C app compatibility usually)
                # But grading.c uses tolower which works on ASCII. 
                # If Chinese characters are involved, simple byte comparison works if encoding matches.
                try:
                    b_user = user_ans.encode('gbk')
                    b_correct = q['answer'].encode('gbk')
                except:
                    b_user = user_ans.encode('utf-8')
                    b_correct = q['answer'].encode('utf-8')
                    
                score = lib.calculate_score(b_user, b_correct, q['score'])
            else:
                # Fallback python implementation
                score = q['score'] if user_ans.strip().lower() == q['answer'].strip().lower() else 0
            
            total_score += score
            results.append({
                'question': q['content'],
                'user_ans': user_ans,
                'correct_ans': q['answer'],
                'score': score,
                'full_score': q['score']
            })
            
        return render_template('result.html', total_score=total_score, results=results)
    
    return render_template('exam.html', questions=questions)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        content = request.form.get('content')
        answer = request.form.get('answer')
        score = request.form.get('score')
        
        if content and answer and score:
            save_question(content, answer, score)
            return redirect(url_for('index'))
            
    return render_template('add.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
