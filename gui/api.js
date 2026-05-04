/**
 * api.js — обёртка над window.pywebview.api
 * Все методы возвращают Promise<dict> с полем ok:bool.
 */
const api = (() => {
  function call(method, ...args) {
    return window.pywebview.api[method](...args);
  }

  return {
    // Сессия
    newResearch:       ()                          => call('new_research'),
    newCalibration:    ()                          => call('new_calibration'),

    // Изображения
    uploadImage:       (filename, b64, context)    => call('upload_image', filename, b64, context),
    deleteImage:       (filename, context)         => call('delete_image', filename, context),
    listImages:        (context)                   => call('list_images', context),
    getImage:          (filename, folder, context) => call('get_image', filename, folder, context),

    // Анализ
    executeResearch:   (calibrationId)             => call('execute_research', calibrationId),
    executeCalibration:()                          => call('execute_calibration'),

    // Калибровки
    getCalibrations:   ()                          => call('get_calibrations'),
    getCalibration:    (id)                        => call('get_calibration', id),
    saveCalibration:   (data)                      => call('save_calibration', data),
    loadCalibration:   (id)                        => call('load_calibration', id),
    deleteCalibration: (id)                        => call('delete_calibration', id),

    // Исследования
    getResearches:     ()                          => call('get_researches'),
    getResearch:       (id)                        => call('get_research', id),
    saveResearch:      (data)                      => call('save_research', data),
    loadResearch:      (id)                        => call('load_research', id),
    deleteResearch:    (id)                        => call('delete_research', id),

    // Справочники
    getMicroscopes:    ()                          => call('get_microscopes'),
    getDivisionPrices: ()                          => call('get_division_prices'),

    // USB-микроскопы
    scanCameras:            ()           => call('scan_cameras'),
    getTestFrame:           (index)      => call('get_test_frame', index),
    saveCustomMicroscope:   (data)       => call('save_custom_microscope', data),
    deleteCustomMicroscope: (id)         => call('delete_custom_microscope', id),
  };
})();
