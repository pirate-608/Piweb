#include "dict.h"

typedef struct SectionInfo {
    int section_id;
    char title[128];
    int level;
    int length;
    double ratio;
    int word_count;
} SectionInfo;

typedef struct Stats {
    int total_chars;
    int en_words;
    int cn_chars;
    int sensitive_count;
    int redundancy_count;
    int punct_count;
    int section_count;
    double richness;
} Stats;

typedef struct AnalyzerContext AnalyzerContext;

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

AnalyzerContext* Analyzer_Create(void);
void Analyzer_Free(AnalyzerContext* ctx);
void Analyzer_AddStopWord(AnalyzerContext* ctx, const char* word);
void Analyzer_AddSensitiveWord(AnalyzerContext* ctx, const char* word);
void Analyzer_AddRedundantWord(AnalyzerContext* ctx, const char* word);
void Analyzer_Process(AnalyzerContext* ctx, const char* text);
Stats Analyzer_GetStats(AnalyzerContext* ctx);
void Analyzer_GetTopWords(AnalyzerContext* ctx, WordFreq* out_arr, int n);
void Analyzer_GetSections(AnalyzerContext* ctx, SectionInfo* out_arr, int n);
EXPORT int analyze_text(const char* content, char* result_json, int buf_size);

#ifdef __cplusplus
}
#endif
#ifndef ANALYZER_COMMON_H
#define ANALYZER_COMMON_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define MAX_WORD_LEN 64       // 单个词最大长度
#define MAX_SECTIONS 100      // 最大章节数
#define HASH_TABLE_SIZE 8192  // 哈希桶大小，适合万字级别文本

typedef enum {
    LANG_UNKNOWN = 0,
    LANG_EN,
    LANG_CN
} Language;

#endif
