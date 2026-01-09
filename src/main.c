#include "common.h"
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

#define HISTORY_FILE "cli_history.txt"

void clear_screen() {
    #ifdef _WIN32
        system("cls");
    #else
        system("clear");
    #endif
}

void pause_console() {
    printf("\n按回车键继续...");
    while (getchar() != '\n');
    getchar(); 
}

// --- Visualization Helpers ---

void print_progress_bar(int current, int total) {
    int bar_width = 40;
    float progress = (float)current / total;
    int pos = (int)(bar_width * progress);

    printf("\r[");
    for (int i = 0; i < bar_width; ++i) {
        if (i < pos) printf("=");
        else if (i == pos) printf(">");
        else printf(" ");
    }
    printf("] %d%% (%d/%d)", (int)(progress * 100.0), current, total);
    fflush(stdout);
}

void draw_box_top(int width) {
    printf("┌");
    for(int i=0; i<width-2; i++) printf("─");
    printf("┐\n");
}

void draw_box_bottom(int width) {
    printf("└");
    for(int i=0; i<width-2; i++) printf("─");
    printf("┘\n");
}

void draw_box_line(const char* text, int width, const char* color) {
    // Simple length calculation (assuming ASCII for alignment, which is tricky with UTF-8 Chinese)
    // For this demo, we'll just print without strict alignment for Chinese text to avoid misalignment
    // or use a simple padding if text is ASCII.
    // A better approach for TUI is to use a library, but here we keep it simple.
    printf("│ %s%s%s\n", color ? color : "", text, color ? ANSI_COLOR_RESET : "");
}

// -----------------------------

void shuffle_questions(Question *array, int n) {
    if (n > 1) {
        for (int i = n - 1; i > 0; i--) {
            int j = rand() % (i + 1);
            Question t = array[i];
            array[i] = array[j];
            array[j] = t;
        }
    }
}

void save_exam_record(int total_score, int max_score, int duration_sec) {
    FILE *fp = fopen(HISTORY_FILE, "a");
    if (fp) {
        time_t now = time(NULL);
        char time_str[64];
        strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", localtime(&now));
        
        if (fprintf(fp, "%s|%d|%d|%d\n", time_str, total_score, max_score, duration_sec) < 0) {
            LOG_ERROR("Failed to write exam record to %s", HISTORY_FILE);
        } else {
            LOG_INFO("Saved exam record: %s, Score: %d/%d", time_str, total_score, max_score);
        }
        fclose(fp);
    } else {
        LOG_ERROR("Failed to open history file %s for appending", HISTORY_FILE);
    }
}

void view_exam_history() {
    clear_screen();
    printf(ANSI_COLOR_CYAN "\n=== 历史考试记录 ===\n" ANSI_COLOR_RESET);
    
    FILE *fp = fopen(HISTORY_FILE, "r");
    if (!fp) {
        LOG_INFO("No history file found at %s", HISTORY_FILE);
        printf("暂无历史记录。\n");
        pause_console();
        return;
    }

    // Read all records to memory for chart
    struct Record {
        char time[64];
        int score;
        int max;
    } records[100];
    int count = 0;

    char line[256];
    while (fgets(line, sizeof(line), fp) && count < 100) {
        char *time_str = strtok(line, "|");
        char *score_str = strtok(NULL, "|");
        char *max_str = strtok(NULL, "|");
        /* char *dur_str = strtok(NULL, "|"); // 已移除未使用变量 */
        
        if (time_str && score_str && max_str) {
            strncpy(records[count].time, time_str, sizeof(records[count].time) - 1);
            records[count].time[sizeof(records[count].time) - 1] = '\0';
            records[count].score = atoi(score_str);
            records[count].max = atoi(max_str);
            count++;
        }
    }
    fclose(fp);

    // Draw Chart
    printf("\n[成绩趋势图]\n\n");
    int max_val = 0;
    for(int i=0; i<count; i++) if(records[i].score > max_val) max_val = records[i].score;
    if (max_val == 0) max_val = 100;

    for (int i = 0; i < count; i++) {
        // Shorten time string for display (e.g., "2023-10-27 10:00:00" -> "10-27 10:00")
        char short_time[20];
        strncpy(short_time, records[i].time + 5, 11); 
        short_time[11] = '\0';

        int bar_len = (int)((float)records[i].score / records[i].max * 30); // Scale to 30 chars
        
        printf("%s │ ", short_time);
        for(int j=0; j<bar_len; j++) printf("█");
        printf(" %d/%d\n", records[i].score, records[i].max);
    }
    printf("\n");
    
    pause_console();
}

void start_exam() {
    clear_screen();
    
    // 优化：使用堆内存分配，避免栈溢出风险 (Question 结构体较大)
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

    // 随机打乱题目顺序
    shuffle_questions(questions, count);

    int total_score = 0;
    int max_score = 0;
    time_t start_time = time(NULL);

    printf(ANSI_COLOR_CYAN "\n>>> 考试开始 (共 %d 题) <<<\n" ANSI_COLOR_RESET, count);

    for (int i = 0; i < count; i++) {
        // Progress Bar
        printf("\n");
        print_progress_bar(i, count);
        printf("\n");

        // 1. 显示题目
        display_question(i, questions[i]);

        // 2. 获取用户输入
        get_user_input(questions[i].user_answer, MAX_STR_LEN);

        // 3. 判分并保存结果
        questions[i].obtained_score = calculate_score(
            questions[i].user_answer, 
            questions[i].correct_answer, 
            questions[i].score
        );

        // 累计分数
        total_score += questions[i].obtained_score;
        max_score += questions[i].score;
    }
    
    // Final progress bar
    printf("\n");
    print_progress_bar(count, count);
    printf("\n");

    time_t end_time = time(NULL);
    int duration = (int)difftime(end_time, start_time);

    // 保存记录
    save_exam_record(total_score, max_score, duration);

    // 4. 考试结束报告
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

    // 5. 显示错题
    display_wrong_questions(questions, count);
    
    free(questions); // 释放内存
    pause_console();
}

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