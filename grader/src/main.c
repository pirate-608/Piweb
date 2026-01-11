#include "common.h"
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

#define HISTORY_FILE "cli_history.txt"


int main() {
#ifdef _WIN32
    SetConsoleOutputCP(65001); // Set console output to UTF-8
#endif
    srand(time(NULL)); // 初始化随机数种子

    char choice_str[10];
    int choice = 0;

    while (1) {
        clear_screen();
        // 主菜单界面
        printf("\n");
        printf(ANSI_COLOR_CYAN "  ╔════════════════════════════════════╗\n");
        printf("  ║      C语言自动评分系统 (CLI)       ║\n");
        printf("  ╠════════════════════════════════════╣\n" ANSI_COLOR_RESET);
        printf("  ║                                    ║\n");
        printf("  ║  " ANSI_COLOR_GREEN "1. 开始考试 (Start Exam)" ANSI_COLOR_RESET "          ║\n");
        printf("  ║  " ANSI_COLOR_GREEN "2. 添加题目 (Add Question)" ANSI_COLOR_RESET "        ║\n");
        printf("  ║  " ANSI_COLOR_GREEN "3. 历史记录 (History & Chart)" ANSI_COLOR_RESET "     ║\n");
        printf("  ║  " ANSI_COLOR_GREEN "4. 退出系统 (Exit)" ANSI_COLOR_RESET "                ║\n");
        printf("  ║                                    ║\n");
        printf(ANSI_COLOR_CYAN "  ╚════════════════════════════════════╝\n" ANSI_COLOR_RESET);
        printf("\n  请选择操作 (1-4): ");

        get_user_input(choice_str, sizeof(choice_str));
        choice = atoi(choice_str);

        switch (choice) {
            case 1:
                start_exam();
                break;
            case 2:
                append_question_to_file(DATA_FILE);
                break;
            case 3:
                view_exam_history();
                break;
            case 4:
                printf("感谢使用，再见！\n");
                return 0;
            default:
                printf(ANSI_COLOR_RED "无效选择，请重试。\n" ANSI_COLOR_RESET);
                pause_console();
        }
    }
    return 0;
}