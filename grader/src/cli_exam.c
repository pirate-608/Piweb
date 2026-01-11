#include "common.h"
#include <time.h>
#include <stdlib.h>
#include <stdio.h>

// 进度条、绘制框等辅助函数声明（main.c 里实现/声明）
void print_progress_bar(int current, int total);
void draw_box_top(int width);
void draw_box_bottom(int width);

void start_exam() {
    clear_screen();
    Question *questions = (Question*)malloc(MAX_QUESTIONS * sizeof(Question));
    if (!questions) {
        LOG_ERROR("Memory allocation failed for questions array");
        pause_console();
        return;
    }
    int count = load_questions(DATA_FILE, questions);
    if (count == 0) {
        printf(ANSI_COLOR_RED "题库为空，请先在主菜单添加题目！\n" ANSI_COLOR_RESET);
        free(questions);
        pause_console();
        return;
    }
    shuffle_questions(questions, count);
    int total_score = 0;
    int max_score = 0;
    time_t start_time = time(NULL);
    printf(ANSI_COLOR_CYAN "\n>>> 考试开始 (共 %d 题) <<<\n" ANSI_COLOR_RESET, count);
    for (int i = 0; i < count; i++) {
        printf("\n");
        print_progress_bar(i, count);
        printf("\n");
        display_question(i, questions[i]);
        get_user_input(questions[i].user_answer, MAX_STR_LEN);
        questions[i].obtained_score = calculate_score(
            questions[i].user_answer, 
            questions[i].correct_answer, 
            questions[i].score
        );
        total_score += questions[i].obtained_score;
        max_score += questions[i].score;
    }
    printf("\n");
    print_progress_bar(count, count);
    printf("\n");
    time_t end_time = time(NULL);
    int duration = (int)difftime(end_time, start_time);
    save_exam_record(total_score, max_score, duration);
    clear_screen();
    draw_box_top(40);
    printf("│        " ANSI_COLOR_MAGENTA "成绩单 (Report Card)" ANSI_COLOR_RESET "          \n");
    printf("│                                      \n");
    printf("│  最终得分: " ANSI_BOLD "%3d" ANSI_COLOR_RESET " / %-3d              \n", total_score, max_score);
    printf("│  考试耗时: %-3d 秒                  \n", duration);
    double percentage = (max_score > 0) ? ((double)total_score / max_score * 100.0) : 0.0;
    printf("│  正确率:   %-5.1f%%                   \n", percentage);
    printf("│                                      \n");
    if (percentage >= 90)      printf("│  评价: " ANSI_COLOR_GREEN "优秀 (Excellent)" ANSI_COLOR_RESET "             \n");
    else if (percentage >= 60) printf("│  评价: " ANSI_COLOR_YELLOW "及格 (Pass)     " ANSI_COLOR_RESET "             \n");
    else                       printf("│  评价: " ANSI_COLOR_RED "不及格 (Fail)   " ANSI_COLOR_RESET "             \n");
    draw_box_bottom(40);
    display_wrong_questions(questions, count);
    free(questions);
    pause_console();
}
