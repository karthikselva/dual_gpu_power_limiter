#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdlib.h>
#include <string.h>

struct Telemetry {
    float cpuUsage;
    float cpuPower;
    float cpuTemp;     // Still parsed but not displayed as per request
    float gpu1Power;
    float gpu1Temp;
    float gpu2Power;
    float gpu2Temp;
    float systemPower;
    int count;
};

// Pure C++ parsing logic
inline bool parseTelemetry(const char* data, Telemetry &out) {
    if (!data || strlen(data) == 0) return false;

    char buf[128];
    strncpy(buf, data, sizeof(buf)-1);
    buf[sizeof(buf)-1] = '\0';

    float vals[8] = {0};
    int count = 0;
    
    char* token = strtok(buf, ",");
    while (token != NULL && count < 8) {
        vals[count++] = atof(token);
        token = strtok(NULL, ",");
    }

    out.count = count;

    if (count == 6) {
        out.cpuUsage = vals[0];
        out.cpuPower = vals[1];
        out.cpuTemp = vals[2];
        out.gpu1Power = vals[3];
        out.gpu1Temp = vals[4];
        out.gpu2Power = 0;
        out.gpu2Temp = 0;
        out.systemPower = vals[5];
        return true;
    } else if (count == 8) {
        out.cpuUsage = vals[0];
        out.cpuPower = vals[1];
        out.cpuTemp = vals[2];
        out.gpu1Power = vals[3];
        out.gpu1Temp = vals[4];
        out.gpu2Power = vals[5];
        out.gpu2Temp = vals[6];
        out.systemPower = vals[7];
        return true;
    }

    return false;
}

#endif
