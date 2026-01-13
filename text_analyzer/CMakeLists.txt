cmake_minimum_required(VERSION 3.10)
project(TextAnalyzer C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# 定义宏以导出 DLL 符号 (Windows)
add_definitions(-DANALYZER_EXPORTS)

include_directories(include)

# 源文件列表
set(LIB_SOURCES
    src/analyzer.c
    src/dict.c
    src/list.c
    src/trie.c
    src/utils.c
)

# 生成动态库
add_library(analyzer SHARED ${LIB_SOURCES})
set_target_properties(analyzer PROPERTIES
    OUTPUT_NAME "analyzer"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/text_analyzer
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/text_analyzer
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/text_analyzer
)
target_link_libraries(analyzer m) # Linux下链接 math 库

if(UNIX)
    target_link_libraries(analyzer pthread)
endif()

# 生成 CLI 可执行文件
add_executable(analyzer_cli src/main.c) 
target_link_libraries(analyzer_cli analyzer)
set_target_properties(analyzer_cli PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/text_analyzer
)

# ========================================================
# 关键步骤：将 dict 文件夹复制到构建目录
# 这样 .exe 运行时，直接访问 ./dict 即可
# ========================================================
file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/dict 
    DESTINATION ${CMAKE_BINARY_DIR}/text_analyzer)

message(STATUS "Dictionary files copied to: ${CMAKE_BINARY_DIR}/text_analyzer/dict")