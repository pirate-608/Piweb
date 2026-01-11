cmake_minimum_required(VERSION 3.10)
project(auto_grader C)

set(CMAKE_C_STANDARD 99)

include_directories(include)
file(GLOB SRC_FILES src/*.c)


# 产物输出到 build/grader 目录，避免 build/build 嵌套
add_executable(auto_grader_cli ${SRC_FILES})
set_target_properties(auto_grader_cli PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/grader)


# 修正 grading 动态库产物路径，确保生成 libgrading.so 到 build/grader/
add_library(grading SHARED src/grading.c)
set_target_properties(grading PROPERTIES
	LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/grader
	OUTPUT_NAME "grading"
)
