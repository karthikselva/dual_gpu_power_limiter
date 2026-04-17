#include <unity.h>
#include "telemetry.h"

void test_parsing_6_values(void) {
    Telemetry t;
    const char* input = "2,22.0,38.9,39.6,40,156.6";
    bool success = parseTelemetry(input, t);
    
    TEST_ASSERT_TRUE(success);
    TEST_ASSERT_EQUAL(6, t.count);
    TEST_ASSERT_EQUAL_FLOAT(2.0, t.cpuUsage);
    TEST_ASSERT_EQUAL_FLOAT(22.0, t.cpuPower);
    TEST_ASSERT_EQUAL_FLOAT(38.9, t.cpuTemp);
    TEST_ASSERT_EQUAL_FLOAT(39.6, t.gpu1Power);
    TEST_ASSERT_EQUAL_FLOAT(40.0, t.gpu1Temp);
    TEST_ASSERT_EQUAL_FLOAT(156.6, t.systemPower);
}

void test_parsing_8_values(void) {
    Telemetry t;
    const char* input = "10,50.5,60.0,200.0,70,150.0,65,550.0";
    bool success = parseTelemetry(input, t);
    
    TEST_ASSERT_TRUE(success);
    TEST_ASSERT_EQUAL(8, t.count);
    TEST_ASSERT_EQUAL_FLOAT(10.0, t.cpuUsage);
    TEST_ASSERT_EQUAL_FLOAT(200.0, t.gpu1Power);
    TEST_ASSERT_EQUAL_FLOAT(150.0, t.gpu2Power);
    TEST_ASSERT_EQUAL_FLOAT(550.0, t.systemPower);
}

void test_parsing_invalid(void) {
    Telemetry t;
    const char* input = "invalid,data";
    bool success = parseTelemetry(input, t);
    TEST_ASSERT_FALSE(success);
}

#ifdef ARDUINO
#include <Arduino.h>
void setup() {
    delay(2000);
    UNITY_BEGIN();
    RUN_TEST(test_parsing_6_values);
    RUN_TEST(test_parsing_8_values);
    RUN_TEST(test_parsing_invalid);
    UNITY_END();
}
void loop() {}
#else
int main(int argc, char **argv) {
    UNITY_BEGIN();
    RUN_TEST(test_parsing_6_values);
    RUN_TEST(test_parsing_8_values);
    RUN_TEST(test_parsing_invalid);
    return UNITY_END();
}
#endif
