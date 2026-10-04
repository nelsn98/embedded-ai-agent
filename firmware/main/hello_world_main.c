#include <stdio.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_timer.h"

// External LED: GPIO4 -> resistor -> LED anode; cathode -> GND.
// Confirm this pin is available on your actual board before wiring.
#define LED_GPIO GPIO_NUM_4
#define LED_INTERVAL_MS 500

void app_main(void)
{
    gpio_config_t config = {
        .pin_bit_mask = 1ULL << LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&config));
    ESP_ERROR_CHECK(gpio_set_level(LED_GPIO, 0));
    printf("BOOT_OK interval_ms=%d gpio=%d\n", LED_INTERVAL_MS, LED_GPIO);
    fflush(stdout);
    int level = 1;
    while (1) {
        ESP_ERROR_CHECK(gpio_set_level(LED_GPIO, level));
        printf("LED_%s timestamp=%" PRId64 "\n",
               level ? "ON" : "OFF", esp_timer_get_time() / 1000);
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(LED_INTERVAL_MS));
        level = !level;
    }
}
