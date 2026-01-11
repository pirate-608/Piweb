#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_QUESTIONS 100
#define MAX_STR_LEN 256
#define DATA_FILE "questions.txt"

// ANSI Color Codes
#define ANSI_COLOR_RED     "\x1b[31m"
#define ANSI_COLOR_GREEN   "\x1b[32m"
#define ANSI_COLOR_YELLOW  "\x1b[33m"
#define ANSI_COLOR_BLUE    "\x1b[34m"
#define ANSI_COLOR_MAGENTA "\x1b[35m"
#define ANSI_COLOR_CYAN    "\x1b[36m"
#define ANSI_COLOR_RESET   "\x1b[0m"
#define ANSI_BOLD          "\x1b[1m"

// Logging Macros
#define LOG_ERROR(fmt, ...) fprintf(stderr, ANSI_COLOR_RED "[ERROR] %s:%d: " fmt ANSI_COLOR_RESET "\n", __FILE__, __LINE__, ##__VA_ARGS__)
#define LOG_INFO(fmt, ...)  fprintf(stderr, ANSI_COLOR_BLUE "[INFO] " fmt ANSI_COLOR_RESET "\n", ##__VA_ARGS__)

// 题目结构体
typedef struct {
    int id;
    char content[MAX_STR_LEN];     // 题目
    char correct_answer[MAX_STR_LEN]; // 标准答案
    int score;                     // 分值
    
    // 以下字段用于考后分析
    char user_answer[MAX_STR_LEN]; // 用户填写的答案
    int obtained_score;            // 用户该题得分
} Question;

// --- 函数声明 ---

// get_data.c
int load_questions(const char* filename, Question* q_array);

// add_questions.c (新增)
void append_question_to_file(const char* filename);

// put_questions.c
void display_question(int index, Question q);
void display_wrong_questions(Question* q_array, int count); // 新增错题显示

// get_answer.c
void get_user_input(char* buffer, int size);

// grading.c
int calculate_score(const char* user_ans, const char* correct_ans, int full_score);

// main.c (CLI 入口)
void start_exam();
void view_exam_history();

// main.c 辅助函数声明
void clear_screen();
void pause_console();
void print_progress_bar(int current, int total);
void draw_box_top(int width);
void draw_box_bottom(int width);
void draw_box_line(const char* text, int width, const char* color);
void shuffle_questions(Question *array, int n);
void save_exam_record(int total_score, int max_score, int duration_sec);

#endif
