#ifndef ANALYZER_H
#define ANALYZER_H

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


// 兼容 main.c 的 API
AnalyzerContext* Analyzer_Create(void);
void Analyzer_Free(AnalyzerContext* ctx);
void Analyzer_AddStopWord(AnalyzerContext* ctx, const char* word);
void Analyzer_AddSensitiveWord(AnalyzerContext* ctx, const char* word);
void Analyzer_AddRedundantWord(AnalyzerContext* ctx, const char* word);
void Analyzer_Process(AnalyzerContext* ctx, const char* text);
Stats Analyzer_GetStats(AnalyzerContext* ctx);
void Analyzer_GetTopWords(AnalyzerContext* ctx, WordFreq* out_arr, int n);
void Analyzer_GetSections(AnalyzerContext* ctx, SectionInfo* out_arr, int n);

#endif

#endif