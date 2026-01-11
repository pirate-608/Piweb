
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

#include "analyzer_common.h"
#include "dict.h"
#include "utils.h" 
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdio.h>
#include <math.h>   

// 提前完整声明struct AnalyzerContext，避免incomplete typedef错误
struct AnalyzerContext {
    Dict* dict_freq;        // 有效词频
    Dict* dict_sensitive_hit; // 命中的敏感词
    // 查找表 (为了快速查找，也使用Hash)
    Dict* set_stop;
    Dict* set_sensitive;
    Dict* set_redundant;
    // 结构
    SectionInfo sections[MAX_SECTIONS];
    int section_idx;
    int current_section_char_count;
    Stats stats;
};

// Python/ctypes调用入口：分析文本，返回统计信息JSON
// content: 输入文本，result_json: 输出缓冲区，buf_size: 缓冲区大小
// 返回0成功，-1失败
EXPORT int analyze_text(const char* content, char* result_json, int buf_size) {
    if (!content || !result_json || buf_size < 128) return -1;
    AnalyzerContext* ctx = Analyzer_Create();
    if (!ctx) return -1;
    Analyzer_Process(ctx, content);
    Stats stats = Analyzer_GetStats(ctx);
    // 章节详情JSON拼接+调试输出
    char sections_json[4096];
    int offset = 0;
    offset += snprintf(sections_json + offset, sizeof(sections_json) - offset, "[");
    for (int i = 0; i <= ctx->section_idx; ++i) {
        printf("[DEBUG] section %d: title='%s', level=%d, length=%d, ratio=%.4f\n", i, ctx->sections[i].title, ctx->sections[i].level, ctx->sections[i].length, ctx->sections[i].ratio);
        int n = snprintf(sections_json + offset, sizeof(sections_json) - offset,
            "%s{\"section_id\":%d,\"title\":\"%s\",\"level\":%d,\"length\":%d,\"ratio\":%.4f}",
            (i > 0) ? "," : "",
            i,
            ctx->sections[i].title,
            ctx->sections[i].level,
            ctx->sections[i].length,
            ctx->sections[i].ratio);
        if (n < 0 || n >= (int)(sizeof(sections_json) - offset)) break;
        offset += n;
    }
    snprintf(sections_json + offset, sizeof(sections_json) - offset, "]");
    printf("[DEBUG] sections_json: %s\n", sections_json);

    int n = snprintf(result_json, buf_size,
        "{\"total_chars\":%d,\"en_words\":%d,\"cn_chars\":%d,\"words\":%d,\"sensitive_count\":%d,\"redundancy_count\":%d,\"punct_count\":%d,\"section_count\":%d,\"richness\":%.2f,\"sections\":%s}",
        stats.total_chars, stats.en_words, stats.cn_chars, stats.en_words + stats.cn_chars, stats.sensitive_count, stats.redundancy_count, stats.punct_count, stats.section_count, stats.richness, sections_json);
    Analyzer_Free(ctx);
    return (n > 0 && n < buf_size) ? 0 : -1;
}


EXPORT AnalyzerContext* Analyzer_Create() {
    AnalyzerContext* ctx = (AnalyzerContext*)calloc(1, sizeof(AnalyzerContext));
    ctx->dict_freq = dict_create();
    ctx->dict_sensitive_hit = dict_create();
    ctx->set_stop = dict_create();
    ctx->set_sensitive = dict_create();
    ctx->set_redundant = dict_create();
    
    // 默认添加一个"未分类"章节
    strcpy(ctx->sections[0].title, "Introduction");
    ctx->sections[0].level = 0;
    ctx->section_idx = 0;
    
    return ctx;
}

EXPORT void Analyzer_Free(AnalyzerContext* ctx) {
    if (!ctx) return;
    dict_free(ctx->dict_freq);
    dict_free(ctx->dict_sensitive_hit);
    dict_free(ctx->set_stop);
    dict_free(ctx->set_sensitive);
    dict_free(ctx->set_redundant);
    free(ctx);
}

EXPORT void Analyzer_AddStopWord(AnalyzerContext* ctx, const char* word) { dict_add(ctx->set_stop, word); }
EXPORT void Analyzer_AddSensitiveWord(AnalyzerContext* ctx, const char* word) { dict_add(ctx->set_sensitive, word); }
EXPORT void Analyzer_AddRedundantWord(AnalyzerContext* ctx, const char* word) { dict_add(ctx->set_redundant, word); }

EXPORT void Analyzer_Process(AnalyzerContext* ctx, const char* text) {
    const unsigned char* p = (const unsigned char*)text;
    char buffer[MAX_WORD_LEN];
    int buf_idx = 0;
    
    // 状态机变量
    bool is_line_start = true;
    
    while (*p) {
        int len = utf8_len(*p);
        // --- 1. 结构分析 (Markdown Header) ---
        if (is_line_start && *p == '#') {
            int level = 0;
            const unsigned char* temp = p;
            while (*temp == '#' && level < 6) { level++; temp++; }
            if (*temp == ' ') {
                ctx->sections[ctx->section_idx].length = ctx->current_section_char_count;
                if (ctx->section_idx < MAX_SECTIONS - 1) {
                    ctx->section_idx++;
                }
                ctx->sections[ctx->section_idx].level = level;
                ctx->current_section_char_count = 0;
                temp++;
                int t_idx = 0;
                while (*temp && *temp != '\n' && t_idx < 127) {
                    ctx->sections[ctx->section_idx].title[t_idx++] = *temp++;
                }
                ctx->sections[ctx->section_idx].title[t_idx] = '\0';
                p = temp;
                if (*p == '\n') { p++; is_line_start = true; }
                continue;
            }
        }
        ctx->stats.total_chars++;
        ctx->current_section_char_count++;
        // --- 2. 分词与统计 ---
        if (len == 1) {
            // ASCII 处理
            if (isalpha(*p)) {
                if (buf_idx < MAX_WORD_LEN - 1) {
                    buffer[buf_idx++] = tolower(*p);
                }
            } else if (isdigit(*p)) {
                // 数字直接跳过，不计入英文单词
            } else {
                // 分隔符，结算英文单词
                if (buf_idx > 0) {
                    buffer[buf_idx] = '\0';
                    // 只要全为字母（a也算单词），数字不算
                    int valid = 1;
                    for (int i = 0; i < buf_idx; ++i) {
                        if (!isalpha((unsigned char)buffer[i])) { valid = 0; break; }
                    }
                    if (valid) {
                        ctx->stats.en_words++;
                        if (dict_get(ctx->set_sensitive, buffer)) {
                            ctx->stats.sensitive_count++;
                            dict_add(ctx->dict_sensitive_hit, buffer);
                        } else if (dict_get(ctx->set_redundant, buffer)) {
                            ctx->stats.redundancy_count++;
                        } else if (!dict_get(ctx->set_stop, buffer)) {
                            dict_add(ctx->dict_freq, buffer);
                        }
                    }
                    buf_idx = 0;
                }
                if (ispunct(*p)) ctx->stats.punct_count++;
            }
            if (*p == '\n') is_line_start = true;
            else is_line_start = false;
            p++;
        } else {
            // 多字节处理 (中文等)
            // 先结算之前的英文缓冲区（如果有）
            if (buf_idx > 0) {
                buffer[buf_idx] = '\0';
                int valid = 1;
                for (int i = 0; i < buf_idx; ++i) {
                    if (!isalpha((unsigned char)buffer[i])) { valid = 0; break; }
                }
                if (valid) {
                    ctx->stats.en_words++;
                    if (!dict_get(ctx->set_stop, buffer)) dict_add(ctx->dict_freq, buffer);
                }
                buf_idx = 0;
            }
            char mb_char[5] = {0};
            for(int i=0; i<len; i++) mb_char[i] = p[i];
            if (is_chinese(p)) {
                ctx->stats.cn_chars++;
                if (dict_get(ctx->set_sensitive, mb_char)) {
                    ctx->stats.sensitive_count++;
                    dict_add(ctx->dict_sensitive_hit, mb_char);
                } else if (dict_get(ctx->set_redundant, mb_char)) {
                    ctx->stats.redundancy_count++;
                } else if (!dict_get(ctx->set_stop, mb_char)) {
                    dict_add(ctx->dict_freq, mb_char);
                }
            } else {
                ctx->stats.punct_count++;
            }
            p += len;
            is_line_start = false;
        }
    }
    // 结算最后一个词
    if (buf_idx > 0) {
        buffer[buf_idx] = '\0';
        int valid = 1;
        for (int i = 0; i < buf_idx; ++i) {
            if (!isalpha((unsigned char)buffer[i])) { valid = 0; break; }
        }
        if (valid) {
            ctx->stats.en_words++;
            if (!dict_get(ctx->set_stop, buffer)) dict_add(ctx->dict_freq, buffer);
        }
    }
    
    // 结算最后一章长度
    ctx->sections[ctx->section_idx].length = ctx->current_section_char_count;
    ctx->stats.section_count = ctx->section_idx + 1;

    // --- 3. 计算占比和丰富度 ---
    
    // 目录占比
    int valid_len_total = 0;
    for (int i=0; i <= ctx->section_idx; i++) valid_len_total += ctx->sections[i].length;
    if (valid_len_total > 0) {
        for (int i=0; i <= ctx->section_idx; i++) {
            ctx->sections[i].ratio = (double)ctx->sections[i].length / valid_len_total;
        }
    }

    // 语言丰富度 (TTR: Type-Token Ratio)
    // Root TTR (RTTR): unique / sqrt(2 * total)
    if (ctx->dict_freq->total_count > 0) {
        ctx->stats.richness = (double)ctx->dict_freq->unique_count / sqrt(2.0 * ctx->dict_freq->total_count);
    } else {
        ctx->stats.richness = 0.0;
    }
}

EXPORT Stats Analyzer_GetStats(AnalyzerContext* ctx) {
    return ctx->stats;
}

EXPORT void Analyzer_GetTopWords(AnalyzerContext* ctx, WordFreq* out_arr, int n) {
    dict_get_top(ctx->dict_freq, out_arr, n);
}

EXPORT void Analyzer_GetSensitiveWords(AnalyzerContext* ctx, WordFreq* out_arr, int n) {
    dict_get_top(ctx->dict_sensitive_hit, out_arr, n);
}

EXPORT void Analyzer_GetSections(AnalyzerContext* ctx, SectionInfo* out_arr, int max_sections) {
    int count = (ctx->section_idx + 1 > max_sections) ? max_sections : ctx->section_idx + 1;
    for (int i=0; i<count; i++) {
        out_arr[i] = ctx->sections[i];
    }
}