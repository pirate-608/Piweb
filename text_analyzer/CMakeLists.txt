cmake_minimum_required(VERSION 3.10)
project(TextAnalyzer C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(include)

file(GLOB SOURCES "src/*.c")

# 生成动态库 .so (Linux/Mac) 或 .dll (Windows)
add_library(analyzer SHARED ${SOURCES})