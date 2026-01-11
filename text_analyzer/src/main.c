#include "../include/analyzer_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

#define TXT_BUF_SIZE (1024 * 1024)

// 读取整个文本文件到buf，返回实际长度
size_t read_txt_file(const char* path, char* buf, size_t maxlen) {
    FILE* fp = fopen(path, "r");
    if (!fp) {
        printf("无法打开文件: %s\n", path);
        return 0;
    }
    size_t len = fread(buf, 1, maxlen - 1, fp);
    buf[len] = '\0';
    fclose(fp);
    return len;
}

void print_stats(const Stats* stats) {
    printf("\n分析结果：\n");
    printf("总字符数: %d\n", stats->total_chars);
    printf("英文单词数: %d\n", stats->en_words);
    printf("中文字符数: %d\n", stats->cn_chars);
    printf("敏感词数: %d\n", stats->sensitive_count);
    printf("冗余词数: %d\n", stats->redundancy_count);
    printf("标点符号数: %d\n", stats->punct_count);
    printf("分段数: %d\n", stats->section_count);
    printf("丰富度: %.2f\n", stats->richness);
}

int main() {
#ifdef _WIN32
    SetConsoleOutputCP(65001); // 设置Windows控制台为UTF-8
#endif
    printf("==== 文本分析器 CLI ====\n");
    char txt_path[512];
    printf("请输入要分析的文件路径(.txt): ");
    if (!fgets(txt_path, sizeof(txt_path), stdin)) {
        printf("读取路径失败\n");
        return 1;
    }
    txt_path[strcspn(txt_path, "\r\n")] = 0;
    if (strlen(txt_path) == 0) {
        printf("未输入路径，程序退出。\n");
        return 1;
    }
    char* buf = (char*)malloc(TXT_BUF_SIZE);
    if (!buf) {
        printf("内存分配失败\n");
        return 1;
    }
    size_t len = read_txt_file(txt_path, buf, TXT_BUF_SIZE);
    if (len == 0) {
        free(buf);
        return 1;
    }
    AnalyzerContext* ctx = Analyzer_Create();
    Analyzer_Process(ctx, buf);
    Stats stats = Analyzer_GetStats(ctx);
    print_stats(&stats);
    Analyzer_Free(ctx);
    free(buf);
    return 0;
}
