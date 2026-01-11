#include "../include/analyzer.h"
#include <stdio.h>
#include <stdlib.h>

int main() {
    AnalyzerContext* ctx = Analyzer_Create();
    // 添加停用词、敏感词、冗余词示例
    Analyzer_AddStopWord(ctx, "the");
    Analyzer_AddSensitiveWord(ctx, "badword");
    Analyzer_AddRedundantWord(ctx, "very");

    // 测试文本
    const char* text = "# 第一章\n这是一个测试文本。very good!\n# 第二章\nThis is a test. The badword is here.";
    Analyzer_Process(ctx, text);

    // 输出统计信息
    Stats stats = Analyzer_GetStats(ctx);
    printf("总字数: %d\n英文单词: %d\n中文字符: %d\n敏感词命中: %d\n冗余词: %d\n标点: %d\n章节数: %d\n丰富度: %.3f\n",
        stats.total_chars, stats.en_words, stats.cn_chars, stats.sensitive_count, stats.redundancy_count, stats.punct_count, stats.section_count, stats.richness);

    // 输出高频词
    WordFreq top_words[10];
    Analyzer_GetTopWords(ctx, top_words, 10);
    printf("\n高频词：\n");
    for(int i=0; i<10 && top_words[i].count>0; i++) {
        printf("%s: %d\n", top_words[i].word, top_words[i].count);
    }

    // 输出章节结构
    SectionInfo sections[10];
    Analyzer_GetSections(ctx, sections, 10);
    printf("\n章节结构：\n");
    for(int i=0; i<stats.section_count && i<10; i++) {
        printf("[%d] %s (level %d): %d字, 占比%.2f\n", i, sections[i].title, sections[i].level, sections[i].length, sections[i].ratio);
    }

    Analyzer_Free(ctx);
    return 0;
}
