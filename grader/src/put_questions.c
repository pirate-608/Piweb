#include "common.h"

void display_question(int index, Question q) {
    printf(ANSI_COLOR_BLUE "\n----------------------------------------\n" ANSI_COLOR_RESET);
    printf(ANSI_BOLD "[第 %d 题] (%d 分)\n" ANSI_COLOR_RESET, index + 1, q.score);
    printf("题目: %s\n", q.content);
    printf(ANSI_COLOR_YELLOW "请输入答案: " ANSI_COLOR_RESET);
}

void display_wrong_questions(Question* q_array, int count) {
    if (!q_array) {
        LOG_ERROR("Invalid q_array passed to display_wrong_questions");
        return;
    }

    printf(ANSI_COLOR_RED "\n================ 错题回顾 ================\n" ANSI_COLOR_RESET);
    int wrong_count = 0;

    for (int i = 0; i < count; i++) {
        // 如果得分小于满分，视为有错误（或未完全正确）
        if (q_array[i].obtained_score < q_array[i].score) {
            wrong_count++;
            printf(ANSI_COLOR_BLUE "----------------------------------------\n" ANSI_COLOR_RESET);
            printf("题目 %d: %s\n", q_array[i].id, q_array[i].content);
            printf(ANSI_COLOR_RED "  [-] 你的回答: %s\n" ANSI_COLOR_RESET, 
                   (strlen(q_array[i].user_answer) > 0) ? q_array[i].user_answer : "(未作答)");
            printf(ANSI_COLOR_GREEN "  [+] 正确答案: %s\n" ANSI_COLOR_RESET, q_array[i].correct_answer);
        }
    }

    if (wrong_count == 0) {
        printf(ANSI_COLOR_GREEN "恭喜！没有错题，全对！\n" ANSI_COLOR_RESET);
    } else {
        printf(ANSI_COLOR_YELLOW "\n共发现 %d 道错题，请复习。\n" ANSI_COLOR_RESET, wrong_count);
    }
    printf(ANSI_COLOR_RED "==========================================\n" ANSI_COLOR_RESET);
}