#include "analyzer.h"
#include "dict.h"
#include "utils.h" 
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdio.h>

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

AnalyzerContext* Analyzer_Create() {
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

void Analyzer_Free(AnalyzerContext* ctx) {
    if (!ctx) return;
    dict_free(ctx->dict_freq);
    dict_free(ctx->dict_sensitive_hit);
    dict_free(ctx->set_stop);
    dict_free(ctx->set_sensitive);
    dict_free(ctx->set_redundant);
    free(ctx);
}

void Analyzer_AddStopWord(AnalyzerContext* ctx, const char* word) { dict_add(ctx->set_stop, word); }
void Analyzer_AddSensitiveWord(AnalyzerContext* ctx, const char* word) { dict_add(ctx->set_sensitive, word); }
void Analyzer_AddRedundantWord(AnalyzerContext* ctx, const char* word) { dict_add(ctx->set_redundant, word); }

void Analyzer_Process(AnalyzerContext* ctx, const char* text) {
    const unsigned char* p = (const unsigned char*)text;
    char buffer[MAX_WORD_LEN];
    int buf_idx = 0;
    
    // 状态机变量
    bool is_line_start = true;
    
    while (*p) {
        int len = utf8_len(*p);
        
        // --- 1. 结构分析 (Markdown Header) ---
        // 简单逻辑：行首遇到 # 且后面有空格
        if (is_line_start && *p == '#') {
            int level = 0;
            const unsigned char* temp = p;
            while (*temp == '#' && level < 6) { level++; temp++; }
            if (*temp == ' ') { // 确认是标题
                // 结算上一章
                ctx->sections[ctx->section_idx].length = ctx->current_section_char_count;
                
                // 开启新章
                if (ctx->section_idx < MAX_SECTIONS - 1) {
                    ctx->section_idx++;
                }
                ctx->sections[ctx->section_idx].level = level;
                ctx->current_section_char_count = 0;
                
                // 提取标题文本
                temp++; // skip space
                int t_idx = 0;
                while (*temp && *temp != '\n' && t_idx < 127) {
                    ctx->sections[ctx->section_idx].title[t_idx++] = *temp++;
                }
                ctx->sections[ctx->section_idx].title[t_idx] = '\0';
                
                // 移动指针到行尾
                p = temp; 
                if (*p == '\n') { p++; is_line_start = true; }
                continue;
            }
        }

        // 统计总字符 (包括换行等)
        ctx->stats.total_chars++;
        ctx->current_section_char_count++;

        // --- 2. 分词与统计 ---
        
        if (len == 1) {
            // ASCII 处理
            if (isalnum(*p)) {
                if (buf_idx < MAX_WORD_LEN - 1) {
                    buffer[buf_idx++] = tolower(*p); // 英文转小写统计
                }
            } else {
                // 分隔符，结算英文单词
                if (buf_idx > 0) {
                    buffer[buf_idx] = '\0';
                    ctx->stats.en_words++;
                    
                    // 检查逻辑
                    if (dict_get(ctx->set_sensitive, buffer)) {
                        ctx->stats.sensitive_count++;
                        dict_add(ctx->dict_sensitive_hit, buffer);
                    } else if (dict_get(ctx->set_redundant, buffer)) {
                        ctx->stats.redundancy_count++;
                    } else if (!dict_get(ctx->set_stop, buffer)) {
                        // 不是停用词，加入词频
                        dict_add(ctx->dict_freq, buffer);
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
                ctx->stats.en_words++;
                // 同样的英文结算逻辑... (省略重复代码，实际编码可用辅助函数)
                if (!dict_get(ctx->set_stop, buffer)) dict_add(ctx->dict_freq, buffer);
                buf_idx = 0;
            }

            // 提取当前多字节字符
            char mb_char[5] = {0};
            for(int i=0; i<len; i++) mb_char[i] = p[i];
            
            if (is_chinese(p)) {
                ctx->stats.cn_chars++;
                
                // 中文单字分析
                if (dict_get(ctx->set_sensitive, mb_char)) {
                    ctx->stats.sensitive_count++;
                    dict_add(ctx->dict_sensitive_hit, mb_char);
                } else if (dict_get(ctx->set_redundant, mb_char)) {
                    ctx->stats.redundancy_count++;
                } else if (!dict_get(ctx->set_stop, mb_char)) {
                    dict_add(ctx->dict_freq, mb_char);
                }
            } else {
                // 其他UTF8符号，视为标点或符号
                ctx->stats.punct_count++;
            }
            
            p += len;
            is_line_start = false;
        }
    }
    
    // 结算最后一个词
    if (buf_idx > 0) {
        buffer[buf_idx] = '\0';
        ctx->stats.en_words++;
        if (!dict_get(ctx->set_stop, buffer)) dict_add(ctx->dict_freq, buffer);
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
    // 简单算法：去重后的有效词 / 总有效词
    if (ctx->dict_freq->total_count > 0) {
        ctx->stats.richness = (double)ctx->dict_freq->unique_count / ctx->dict_freq->total_count;
    } else {
        ctx->stats.richness = 0.0;
    }
}

Stats Analyzer_GetStats(AnalyzerContext* ctx) {
    return ctx->stats;
}

void Analyzer_GetTopWords(AnalyzerContext* ctx, WordFreq* out_arr, int n) {
    dict_get_top(ctx->dict_freq, out_arr, n);
}

void Analyzer_GetSensitiveWords(AnalyzerContext* ctx, WordFreq* out_arr, int n) {
    dict_get_top(ctx->dict_sensitive_hit, out_arr, n);
}

void Analyzer_GetSections(AnalyzerContext* ctx, SectionInfo* out_arr, int max_sections) {
    int count = (ctx->section_idx + 1 > max_sections) ? max_sections : ctx->section_idx + 1;
    for (int i=0; i<count; i++) {
        out_arr[i] = ctx->sections[i];
    }
}