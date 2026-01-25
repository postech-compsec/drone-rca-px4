# build (C++17; change to clang++ if you like)
clang++ -std=c++17 -O2 -Wall -Wextra -pedantic create_plan_files.cpp -o create_plan_files

# usage:
#   create_plan_files <count> <output_dir> [vehicleType]
#     vehicleType (optional): 1=fixed-wing, 2=multirotor; default: random {1,2}
