#include "common.h"
#include <stdio.h>
#include <string.h>

#define HISTORY_FILE "cli_history.txt"

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
        if (time_str && score_str && max_str) {
            strncpy(records[count].time, time_str, sizeof(records[count].time) - 1);
            records[count].time[sizeof(records[count].time) - 1] = '\0';
            records[count].score = atoi(score_str);
            records[count].max = atoi(max_str);
            count++;
        }
    }
    fclose(fp);
    printf("\n[成绩趋势图]\n\n");
    int max_val = 0;
    for(int i=0; i<count; i++) if(records[i].score > max_val) max_val = records[i].score;
    if (max_val == 0) max_val = 100;
    for (int i = 0; i < count; i++) {
        char short_time[20];
        strncpy(short_time, records[i].time + 5, 11); 
        short_time[11] = '\0';
        int bar_len = (int)((float)records[i].score / records[i].max * 30);
        printf("%s │ ", short_time);
        for(int j=0; j<bar_len; j++) printf("█");
        printf(" %d/%d\n", records[i].score, records[i].max);
    }
    printf("\n");
    pause_console();
}
