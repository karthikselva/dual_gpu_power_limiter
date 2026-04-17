#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdlib.h>
#include <string.h>

struct Telemetry {
    float cpuUsage;
    float cpuPower;
    float cpuTemp;
    float gpu1Power, gpu1Temp, gpu1Limit;
    float gpu2Power, gpu2Temp, gpu2Limit;
    float systemPower;
    int count;
};

inline bool parseTelemetry(const char* data, Telemetry &out) {
    if (!data || strlen(data) == 0) return false;

    char buf[160]; // Increased buffer for more values
    strncpy(buf, data, sizeof(buf)-1);
    buf[sizeof(buf)-1] = '\0';

    float vals[12] = {0};
    int count = 0;
    
    char* token = strtok(buf, ",");
    while (token != NULL && count < 12) {
        vals[count++] = atof(token);
        token = strtok(NULL, ",");
    }

    out.count = count;

    if (count == 6) {
        out.cpuUsage = vals[0]; out.cpuPower = vals[1]; out.cpuTemp = vals[2];
        out.gpu1Power = vals[3]; out.gpu1Temp = vals[4]; out.gpu1Limit = 0;
        out.gpu2Power = 0; out.gpu2Temp = 0; out.gpu2Limit = 0;
        out.systemPower = vals[5];
        return true;
    } else if (count == 8) {
        out.cpuUsage = vals[0]; out.cpuPower = vals[1]; out.cpuTemp = vals[2];
        out.gpu1Power = vals[3]; out.gpu1Temp = vals[4]; out.gpu1Limit = 0;
        out.gpu2Power = vals[5]; out.gpu2Temp = vals[6]; out.gpu2Limit = 0;
        out.systemPower = vals[7];
        return true;
    } else if (count == 10) {
        // Format: Usage,CpuPwr,CpuTemp,G1P,G1T,G1L,G2P,G2T,G2L,SysPwr
        out.cpuUsage = vals[0]; out.cpuPower = vals[1]; out.cpuTemp = vals[2];
        out.gpu1Power = vals[3]; out.gpu1Temp = vals[4]; out.gpu1Limit = vals[5];
        out.gpu2Power = vals[6]; out.gpu2Temp = vals[7]; out.gpu2Limit = vals[8];
        out.systemPower = vals[9];
        return true;
    }

    return false;
}

#endif
