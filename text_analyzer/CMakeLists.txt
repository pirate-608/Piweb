cmake_minimum_required(VERSION 3.10)
project(TextAnalyzer C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(include)

file(GLOB SOURCES "src/*.c")


# 生成动态库 .so (Linux/Mac) 或 .dll (Windows)，并确保产物名为 libanalyzer，输出到 build/text_analyzer/

add_library(analyzer SHARED ${SOURCES})
set_target_properties(analyzer PROPERTIES
	OUTPUT_NAME "analyzer"
	LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/text_analyzer
)
target_link_libraries(analyzer m)

# 生成CLI可执行文件
add_executable(analyzer_cli src/main.c)
target_link_libraries(analyzer_cli analyzer m)