// Offline converter evidence only: build against the exact documented llama.cpp pin.
#include "json-schema-to-grammar.h"
#include <cstdlib>
#include <iostream>

// Assert failure stays fatal. No model/backend library is loaded by this harness.
extern "C" void ggml_abort(const char *, int, const char *, ...) { std::abort(); }

int main() {
    const std::string raw((std::istreambuf_iterator<char>(std::cin)), {});
    const auto config = common_json::parse(raw);
    std::cout << json_schema_to_grammar(config.at("output_schema"));
}
