#include "common.h"

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

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
    printf("│ %s%s%s\n", color ? color : "", text, color ? ANSI_COLOR_RESET : "");
}

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
    FILE *fp = fopen("cli_history.txt", "a");
    if (fp) {
        time_t now = time(NULL);
        char time_str[64];
        strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", localtime(&now));
        if (fprintf(fp, "%s|%d|%d|%d\n", time_str, total_score, max_score, duration_sec) < 0) {
            LOG_ERROR("Failed to write exam record to %s", "cli_history.txt");
        } else {
            LOG_INFO("Saved exam record: %s, Score: %d/%d", time_str, total_score, max_score);
        }
        fclose(fp);
    } else {
        LOG_ERROR("Failed to open history file %s for appending", "cli_history.txt");
    }
}
