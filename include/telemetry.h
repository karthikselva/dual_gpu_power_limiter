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
    float peakCpuPwr, peakG1Pwr, peakG2Pwr, peakSysPwr;
    char time[8];
    int count;
};

inline bool parseTelemetry(const char* data, Telemetry &out) {
    if (!data || strlen(data) == 0) return false;

    char buf[200]; // Increased buffer for even more values
    strncpy(buf, data, sizeof(buf)-1);
    buf[sizeof(buf)-1] = '\0';

    char* vals[16];
    int count = 0;
    
    char* token = strtok(buf, ",");
    while (token != NULL && count < 16) {
        vals[count++] = token;
        token = strtok(NULL, ",");
    }

    out.count = count;
    memset(out.time, 0, sizeof(out.time));

    if (count == 6) {
        out.cpuUsage = atof(vals[0]); out.cpuPower = atof(vals[1]); out.cpuTemp = atof(vals[2]);
        out.gpu1Power = atof(vals[3]); out.gpu1Temp = atof(vals[4]); out.gpu1Limit = 0;
        out.gpu2Power = 0; out.gpu2Temp = 0; out.gpu2Limit = 0;
        out.systemPower = atof(vals[5]);
        return true;
    } else if (count == 8) {
        out.cpuUsage = atof(vals[0]); out.cpuPower = atof(vals[1]); out.cpuTemp = atof(vals[2]);
        out.gpu1Power = atof(vals[3]); out.gpu1Temp = atof(vals[4]); out.gpu1Limit = 0;
        out.gpu2Power = atof(vals[5]); out.gpu2Temp = atof(vals[6]); out.gpu2Limit = 0;
        out.systemPower = atof(vals[7]);
        return true;
    } else if (count == 10) {
        out.cpuUsage = atof(vals[0]); out.cpuPower = atof(vals[1]); out.cpuTemp = atof(vals[2]);
        out.gpu1Power = atof(vals[3]); out.gpu1Temp = atof(vals[4]); out.gpu1Limit = atof(vals[5]);
        out.gpu2Power = atof(vals[6]); out.gpu2Temp = atof(vals[7]); out.gpu2Limit = atof(vals[8]);
        out.systemPower = atof(vals[9]);
        return true;
    } else if (count >= 11) {
        // Format: Usage,CpuPwr,CpuTemp,G1P,G1T,G1L,G2P,G2T,G2L,SysPwr,PeakCpu,PeakG1,PeakG2,PeakSys,Time
        out.cpuUsage = atof(vals[0]); out.cpuPower = atof(vals[1]); out.cpuTemp = atof(vals[2]);
        out.gpu1Power = atof(vals[3]); out.gpu1Temp = atof(vals[4]); out.gpu1Limit = atof(vals[5]);
        out.gpu2Power = atof(vals[6]); out.gpu2Temp = atof(vals[7]); out.gpu2Limit = atof(vals[8]);
        out.systemPower = atof(vals[9]);
        
        if (count >= 14) {
            out.peakCpuPwr = atof(vals[10]);
            out.peakG1Pwr = atof(vals[11]);
            out.peakG2Pwr = atof(vals[12]);
            out.peakSysPwr = atof(vals[13]);
        }
        
        if (count == 11) {
            strncpy(out.time, vals[10], sizeof(out.time)-1);
        } else if (count == 15) {
            strncpy(out.time, vals[14], sizeof(out.time)-1);
        }
        return true;
    }

    return false;
}

#endif
