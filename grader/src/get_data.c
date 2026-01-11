#include "common.h"

int load_questions(const char* filename, Question* q_array) {
    if (!filename || !q_array) {
        LOG_ERROR("Invalid arguments passed to load_questions");
        return 0;
    }

    FILE* file = fopen(filename, "r");
    if (!file) {
        // 安全改进：不再自动创建文件，避免覆盖风险
        LOG_INFO("Data file not found or unreadable. Starting with empty question set.");
        return 0;
    }

    char line[MAX_STR_LEN * 3];
    int count = 0;

    while (count < MAX_QUESTIONS && fgets(line, sizeof(line), file)) {
        // 安全改进：检查行是否过长
        size_t len = strlen(line);
        if (len > 0 && line[len-1] != '\n' && !feof(file)) {
            LOG_ERROR("Line too long in data file, skipping.");
            // 消耗掉剩余的行内容
            int c;
            while ((c = fgetc(file)) != '\n' && c != EOF);
            continue;
        }

        // 跳过空行
        if (len < 2) continue;

        line[strcspn(line, "\n")] = 0;

        // 安全改进：使用手动解析代替 strtok
        char *current = line;
        char *next_token;
        
        // 1. Content
        next_token = strchr(current, '|');
        if (!next_token) {
            LOG_ERROR("Malformed line (missing separator 1): %s", line);
            continue;
        }
        *next_token = '\0'; // 分割字符串
        
        q_array[count].id = count + 1;
        strncpy(q_array[count].content, current, MAX_STR_LEN - 1);
        q_array[count].content[MAX_STR_LEN - 1] = '\0';
        
        current = next_token + 1;

        // 2. Answer
        next_token = strchr(current, '|');
        if (!next_token) {
            LOG_ERROR("Malformed line (missing separator 2) for question ID %d", q_array[count].id);
            continue;
        }
        *next_token = '\0';

        strncpy(q_array[count].correct_answer, current, MAX_STR_LEN - 1);
        q_array[count].correct_answer[MAX_STR_LEN - 1] = '\0';

        current = next_token + 1;

        // 3. Score (安全改进：使用 strtol)
        char *endptr;
        long val = strtol(current, &endptr, 10);
        if (current == endptr) {
             LOG_ERROR("Invalid score format for question ID %d", q_array[count].id);
             continue;
        }
        q_array[count].score = (int)val;

        // 初始化考试状态字段
        q_array[count].obtained_score = 0;
        memset(q_array[count].user_answer, 0, MAX_STR_LEN);

        count++;
    }

    if (ferror(file)) {
        LOG_ERROR("Error reading from file: %s", filename);
    }

    fclose(file);
    LOG_INFO("Loaded %d questions from %s", count, filename);
    return count;
}