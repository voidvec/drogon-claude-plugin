# drogon-gen-test

生成 drogon DROGON_TEST 测试用例。

## When to use

When writing test cases for a drogon application, use this skill to quickly generate test code that follows drogon testing framework conventions.

## Input parameters

- `test_name`: Test name
- `test_type`: Test type (`unit`, `integration`, `async_db`)
- `assertions`: Assertion description (e.g. `status=200, body contains "success"`)

## Output

1. `DROGON_TEST(TestName)` test case
2. Appropriate assertions (`CHECK` vs `REQUIRE` vs `MANDATE`)
3. Async test pattern (if needed)
4. Test data setup and cleanup code

## Example

```
/drogon-gen-test test_name=UserLogin test_type=integration assertions="status=200, body contains token"
```

Generates a user login integration test.
