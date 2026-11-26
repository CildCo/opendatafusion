<template>
  <div class="app-page">
    <div class="head">
      <el-button link @click="$router.push('/apps')":aria-label="t('common.back')">←</el-button>
      <el-input v-model="name" size="small" style="width: 220px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? t("aedit.published") : t("aedit.draft") }}
      </el-tag>
      <favorite-button type="app" :id="id" />
      <div class="spacer" />
      <history-controls :can-undo="canUndo" :can-redo="canRedo"
                        @undo="history.undo" @redo="history.redo" />
      <el-button size="small" @click="save()">{{ t("aedit.save") }}</el-button>
      <el-button size="small" @click="validate">
        {{ t("aedit.validate") }}
      </el-button>
      <el-button size="small" :loading="loadingData" @click="refresh">
        {{ t("aedit.refreshData") }}
      </el-button>
      <el-button size="small" type="primary" @click="publish">
        {{ t("aedit.publish") }}
      </el-button>
      <el-button size="small" @click="governanceOpen = true">
        {{ t("gov.button") }}
      </el-button>
      <el-button size="small" @click="versionsOpen = true">
        {{ t("aedit.versions") }}
      </el-button>
      <el-button size="small" :disabled="!published"
                 @click="$router.push(`/apps/${id}/run`)">
        {{ t("aedit.run") }}
      </el-button>
      <ShareDialog kind="apps" :asset-id="id" :published="published" />
    </div>

    <div class="body">
      <aside class="left">
        <div class="section">
          <div class="section-head">
            <span>{{ t("aedit.pages") }}</span>
            <el-button link size="small" @click="addPage">
              {{ t("aedit.addPage") }}
            </el-button>
          </div>
          <div class="pages">
            <div v-for="p in content.pages" :key="p.id" class="page-row"
                 :class="{ active: p.id === currentId }"
                 @click="currentId = p.id">
              <span class="page-title">{{ p.title || p.id }}</span>
              <el-tag v-if="content.start_page === p.id" size="small"
                      type="success">{{ t("aedit.homePage") }}</el-tag>
            </div>
          </div>
          <div v-if="currentPage" class="page-actions">
            <el-input v-model="currentPage.title" size="small"
                      :placeholder="t('aedit.pageTitle')" />
            <el-select :model-value="currentPage.visible_roles || []"
                       multiple clearable size="small" style="width: 100%"
                       :placeholder="t('aedit.pageRolesAll')"
                       @update:model-value="setPageRoles">
              <el-option v-for="r in formRoles" :key="r" :value="r"
                         :label="t('role.' + r)" />
            </el-select>
            <el-button link size="small" :disabled="content.start_page ===
              currentPage.id" @click="content.start_page = currentPage.id">
              {{ t("aedit.setHome") }}
            </el-button>
            <el-button link type="danger" size="small"
                       :disabled="content.pages.length <= 1"
                       @click="removePage">
              {{ t("aedit.removePage") }}
            </el-button>
          </div>
        </div>

        <div class="section" v-if="currentPage">
          <div class="section-head">
            <span>{{ t("aedit.pageParams") }}</span>
            <el-button link size="small" @click="addParam">
              {{ t("aedit.addParam") }}
            </el-button>
          </div>
          <div v-for="(p, i) in currentPage.params" :key="i" class="param">
            <el-input v-model="p.name" size="small" placeholder="name"
                      @change="resetParams" />
            <el-select v-model="p.type" size="small" style="width: 92px"
                       @change="resetParams">
              <el-option v-for="pty in paramTypes" :key="pty" :value="pty"
                         :label="pty" />
            </el-select>
            <el-input v-model="p.default" size="small"
                      :placeholder="t('aedit.defaultValue')"
                      @change="resetParams" />
            <el-checkbox v-model="p.required" size="small">
              {{ t("aedit.required") }}
            </el-checkbox>
            <el-button link type="danger" size="small"
                       @click="removeParam(i)":aria-label="t('common.remove')">×</el-button>
          </div>
          <p class="hint">{{ t("aedit.paramHint") }}</p>
        </div>

        <div class="section" v-if="currentPage">
          <div class="section-head">
            <span>{{ t("aedit.components") }}</span>
            <el-button link size="small" @click="autoLayout">
              {{ t("aedit.autoLayout") }}
            </el-button>
          </div>
          <div class="palette">
            <el-button v-for="ct in types" :key="ct.type" size="small"
                       class="add" @click="addComponent(ct.type)">
              + {{ t(ct.labelKey) }}
            </el-button>
          </div>
          <div class="add-target">
            <span>{{ t("aedit.addTo") }}</span>
            <el-select v-model="addTarget" size="small" filterable
                       style="flex: 1">
              <el-option v-for="opt in addTargets" :key="opt.value"
                         :value="opt.value" :label="opt.label" />
            </el-select>
          </div>
          <el-input v-model="outlineQuery" size="small" clearable
                    :placeholder="t('aedit.outlineSearch')"
                    class="outline-search" />
          <div class="components">
            <div v-for="row in visibleOutline" :key="row.comp.id"
                 class="comp-row" draggable="true"
                 :class="{ active: row.comp.id === selectedId,
                           nested: row.depth > 0 }"
                 :style="{ paddingLeft: `${8 + row.depth * 14}px` }"
                 @click="selectComponent(row.comp.id)"
                 @dragstart="dragRow = row" @dragover.prevent
                 @drop.prevent="dropComponent(row)"
                 @dragend="dragRow = null">
              <span class="drag-handle">⋮⋮</span>
              <span class="comp-name">{{ rowLabel(row.comp) }}</span>
              <span v-if="row.tabId" class="comp-type">
                {{ row.tabId }}
              </span>
              <span class="comp-type">{{ typeLabel(row.comp.type) }}</span>
              <span class="comp-actions">
                <el-button link size="small"
                           :disabled="row.list.indexOf(row.comp) === 0"
                           @click.stop="moveComponent(row, -1)">↑</el-button>
                <el-button link size="small"
                           :disabled="row.list.indexOf(row.comp)
                             === row.list.length - 1"
                           @click.stop="moveComponent(row, 1)">↓</el-button>
              </span>
            </div>
            <el-empty v-if="!visibleOutline.length"
                      :description="t('aedit.noComponents')" :image-size="48" />
          </div>
        </div>
      </aside>

      <main class="canvas" v-loading="loadingData">
        <div class="canvas-toolbar">
          <el-radio-group v-model="previewDevice" size="small">
            <el-radio-button value="desktop">
              {{ t("aedit.desktop") }}
            </el-radio-button>
            <el-radio-button value="tablet">
              {{ t("aedit.tablet") }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="canvas-frame"
             :class="{ tablet: previewDevice === 'tablet' }">
          <div v-if="currentPage?.params?.length" class="preview-filters">
            <div v-for="p in currentPage.params" :key="p.name" class="filter">
              <span>{{ p.name }}</span>
              <el-input v-model="paramValues[p.name]" size="small"
                        style="width: 130px" :placeholder="p.example || p.type"
                        @change="refresh" />
            </div>
          </div>
          <AppCanvas v-if="currentPage" :key="currentPage.id" design
                     :page="currentPage" :data="data" :params="paramValues"
                     :component-state="previewComponents"
                     :stacked="previewDevice === 'tablet'"
                     :selected-id="selectedId" :on-submit="submitForm"
                     @select="selectComponent"
                     @drag-start="history.pause"
                     @change-end="onCanvasChangeEnd"
                     @navigate="navigatePreview" @row="openPreviewRow"
                     @component-change="onPreviewComponentChange" />
        </div>
      </main>

      <aside class="config">
        <template v-if="selected">
          <div class="config-head">
            <h4>{{ typeLabel(selected.type) }} {{ t("aedit.config") }}</h4>
            <el-button link type="danger" @click="removeComponent">
              {{ t("aedit.delete") }}
            </el-button>
          </div>
          <div class="config-tabs">
            <button v-for="tab in configTabs" :key="tab.key" type="button"
                    class="config-tab"
                    :class="{ active: configTab === tab.key }"
                    @click="configTab = tab.key">
              {{ t(tab.label) }}
            </button>
          </div>
          <div v-show="configTab === 'content'">
          <el-form label-width="76px" size="small">
            <el-form-item :label="t('aedit.title')">
              <el-input v-model="selected.title" />
            </el-form-item>
            <template v-if="['text', 'heading'].includes(selected.type)">
              <el-form-item :label="t('aedit.text')">
                <el-input v-model="selected.text" type="textarea"
                          :rows="selected.type === 'heading' ? 2 : 6" />
              </el-form-item>
              <el-form-item :label="t('aedit.insertBinding')">
                <div class="binding-row">
                  <el-select v-model="bindingPick" size="small" filterable
                             style="flex: 1"
                             :placeholder="t('aedit.bindingPick')">
                    <el-option v-for="opt in bindingOptions" :key="opt.value"
                               :value="opt.value" :label="opt.label" />
                  </el-select>
                  <el-button size="small" :disabled="!bindingPick"
                             @click="insertBinding">
                    {{ t("aedit.insert") }}
                  </el-button>
                </div>
              </el-form-item>
              <p class="hint">{{ t("aedit.bindingHint") }}</p>
            </template>
            <template v-if="selected.type === 'image'">
              <el-form-item :label="t('aedit.imageUrl')">
                <el-input v-model="selected.url" placeholder="https://..." />
              </el-form-item>
              <el-form-item :label="t('aedit.imageAlt')">
                <el-input v-model="selected.alt" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'button'">
              <el-form-item :label="t('aedit.buttonLabel')">
                <el-input v-model="selected.label" />
              </el-form-item>
              <p class="hint">{{ t("aedit.buttonHint") }}</p>
            </template>
            <template v-if="selected.type === 'upload'">
              <el-form-item :label="t('aedit.buttonLabel')">
                <el-input v-model="selected.label" />
              </el-form-item>
              <el-form-item :label="t('aedit.uploadAccept')">
                <el-input :model-value="(selected.accept || []).join(',')"
                          :placeholder="t('aedit.uploadAcceptHint')"
                          @update:model-value="setAccept" />
              </el-form-item>
              <el-form-item :label="t('aedit.uploadMaxMb')">
                <el-input-number v-model="selected.max_mb" :min="1" :max="20" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'approval'">
              <el-form-item :label="t('aedit.title')">
                <el-input v-model="selected.title" />
              </el-form-item>
              <el-form-item :label="t('aedit.rowCount')">
                <el-input-number v-model="selected.limit" :min="1"
                                 :max="50" />
              </el-form-item>
              <p class="hint">{{ t("aedit.approvalHint") }}</p>
            </template>
            <template v-if="selected.type === 'list'">
              <el-form-item :label="t('aedit.dataset')">
                <el-select v-model="selected.dataset_id" filterable
                           style="width: 100%"
                           @change="selectDataset(selected.dataset_id)">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.columns')">
                <el-input v-model="columnsText"
                          :placeholder="t('aedit.columnsHint')" />
              </el-form-item>
              <el-form-item :label="t('aedit.listTitleColumn')">
                <el-select v-model="selected.title_column" clearable
                           style="width: 100%">
                  <el-option v-for="c in listColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.listSubtitleColumn')">
                <el-select v-model="selected.subtitle_column" clearable
                           style="width: 100%">
                  <el-option v-for="c in listColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.listValueColumn')">
                <el-select v-model="selected.value_column" clearable
                           style="width: 100%">
                  <el-option v-for="c in listColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.rowCount')">
                <el-input-number v-model="selected.limit" :min="1"
                                 :max="1000" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'progress'">
              <el-form-item :label="t('aedit.progressValue')">
                <el-input-number v-model="selected.value" :min="0"
                                 :max="100" />
              </el-form-item>
              <el-form-item :label="t('aedit.progressParam')">
                <el-select v-model="selected.value_param" clearable
                           style="width: 100%">
                  <el-option v-for="p in currentPage.params || []"
                             :key="p.name" :value="p.name" :label="p.name" />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selected.type === 'metric'">
              <el-form-item :label="t('aedit.metric')">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%"
                           @change="selectMetric(selected.metric_id)">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.valueColumn')">
                <el-select v-model="selected.value_column" filterable clearable
                           style="width: 100%">
                  <el-option v-for="c in modelColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selected.type === 'form'">
              <el-form-item :label="t('aedit.dataset')">
                <el-select v-model="selected.dataset_id" filterable
                           style="width: 100%"
                           @change="selectFormDataset(selected.dataset_id)">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.mode')">
                <el-select v-model="selected.mode" style="width: 100%"
                           @change="onFormModeChange">
                  <el-option value="insert" :label="t('aedit.modeInsert')" />
                  <el-option value="update" :label="t('aedit.modeUpdate')" />
                  <el-option value="delete" :label="t('aedit.modeDelete')" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.allowRoles')">
                <el-select :model-value="selected.allow_roles || []"
                           multiple clearable
                           :placeholder="t('aedit.allByDefault')"
                           style="width: 100%"
                           @update:model-value="setRoles">
                  <el-option v-for="r in formRoles" :key="r" :value="r"
                             :label="t('role.' + r)" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="['update','delete'].includes(selected.mode)"
                            :label="t('aedit.primaryKey')">
                <el-select v-model="selected.key" filterable
                           allow-create style="width: 100%">
                  <el-option v-for="c in formColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.fields')">
                <div class="filter-list">
                  <div v-for="(f, i) in selected.fields || []" :key="i"
                       class="field-row">
                    <el-select v-model="f.column" size="small" filterable
                               allow-create :placeholder="t('aedit.column')"
                               style="width: 88px">
                      <el-option v-for="c in formColumns" :key="c" :value="c"
                                 :label="c" />
                    </el-select>
                    <el-input v-model="f.label" size="small"
                              :placeholder="t('aedit.label')"
                              style="width: 70px" />
                    <el-select v-model="f.widget" size="small"
                               style="width: 84px">
                      <el-option v-for="w in formWidgets" :key="w"
                                 :value="w" :label="w" />
                    </el-select>
                    <el-checkbox v-model="f.required" size="small">
                      {{ t("aedit.required") }}
                    </el-checkbox>
                    <el-button link type="danger" size="small"
                               @click="removeField(i)":aria-label="t('common.remove')">×</el-button>
                    <el-input v-if="f.widget === 'select'" size="small"
                              :model-value="(f.options || []).join(',')"
                              :placeholder="t('aedit.optionsHint')"
                              @update:model-value="setOptions(f, $event)" />
                  </div>
                  <el-button link size="small" @click="addField">
                    {{ t("aedit.addField") }}
                  </el-button>
                  <p v-if="selected.mode === 'delete'" class="hint">
                    {{ t("aedit.deleteFormHint") }}
                  </p>
                </div>
              </el-form-item>
              <el-form-item :label="t('aedit.button')">
                <el-input v-model="selected.submit_text"
                          :placeholder="t('aedit.submit')" />
              </el-form-item>
              <el-form-item :label="t('aedit.successMessage')">
                <el-input v-model="selected.success_message"
                          :placeholder="t('aedit.submitSuccess')" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'table'">
              <el-form-item :label="t('aedit.dataset')">
                <el-select v-model="selected.dataset_id" filterable clearable
                           style="width: 100%"
                           @change="selectDataset(selected.dataset_id)">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.metric')">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%"
                           @change="selectMetric(selected.metric_id)">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('aedit.columns')">
                <el-input v-model="columnsText"
                          :placeholder="t('aedit.columnsHint')" />
              </el-form-item>
              <el-form-item :label="t('aedit.rowCount')">
                <el-input-number v-model="selected.limit" :min="1"
                                 :max="10000" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'modal'">
              <el-form-item :label="t('aedit.buttonLabel')">
                <el-input v-model="selected.label" />
              </el-form-item>
              <el-form-item :label="t('aedit.title')">
                <el-input v-model="selected.title" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'tabs'">
              <el-form-item :label="t('aedit.compTabs')">
                <div class="tab-list">
                  <div v-for="(tab, i) in selected.tabs || []" :key="tab.id"
                       class="tab-row">
                    <el-input v-model="tab.title" size="small" />
                    <el-button link type="danger" size="small"
                               :disabled="(selected.tabs || []).length <= 1"
                               @click="removeTab(selected, i)"
                               :aria-label="t('common.remove')">×</el-button>
                  </div>
                  <el-button link size="small" @click="addTab(selected)">
                    {{ t("aedit.addTab") }}
                  </el-button>
                </div>
              </el-form-item>
            </template>
          </el-form>
          </div>
          <div v-show="configTab === 'layout' && selected.layout"
               class="layout-box">
            <h4>{{ t("aedit.layout") }}</h4>
            <div class="layout-grid">
              <el-input-number v-model="selected.layout.x" :min="0" :max="11"
                               size="small" :controls="false"
                               :aria-label="t('aedit.layoutX')" />
              <el-input-number v-model="selected.layout.y" :min="0"
                               size="small" :controls="false"
                               :aria-label="t('aedit.layoutY')" />
              <el-input-number v-model="selected.layout.w" :min="1" :max="12"
                               size="small" :controls="false"
                               :aria-label="t('aedit.layoutW')" />
              <el-input-number v-model="selected.layout.h" :min="1"
                               size="small" :controls="false"
                               :aria-label="t('aedit.layoutH')" />
            </div>
            <p class="hint">{{ t("aedit.layoutHint") }}</p>
            <div class="style-box">
              <h4>{{ t("aedit.style") }}</h4>
              <div class="style-grid">
                <div class="style-field">
                  <span>{{ t("aedit.styleBackground") }}</span>
                  <el-color-picker color-format="hex" size="small"
                                   :model-value="selected.style?.background || ''"
                                   @change="setStyle('background', $event)" />
                </div>
                <div class="style-field">
                  <span>{{ t("aedit.styleColor") }}</span>
                  <el-color-picker color-format="hex" size="small"
                                   :model-value="selected.style?.color || ''"
                                   @change="setStyle('color', $event)" />
                </div>
                <div class="style-field">
                  <span>{{ t("aedit.styleAlign") }}</span>
                  <el-select size="small"
                             :model-value="selected.style?.align || ''"
                             clearable
                             @update:model-value="setStyle('align', $event)">
                    <el-option value="left" :label="t('aedit.styleLeft')" />
                    <el-option value="center" :label="t('aedit.styleCenter')" />
                    <el-option value="right" :label="t('aedit.styleRight')" />
                  </el-select>
                </div>
                <div class="style-field">
                  <span>{{ t("aedit.stylePadding") }}</span>
                  <el-input-number size="small" :min="0" :max="64"
                                   :controls="false"
                                   :model-value="selected.style?.padding"
                                   @update:model-value="setStyle('padding', $event)" />
                </div>
                <div class="style-field">
                  <span>{{ t("aedit.styleRadius") }}</span>
                  <el-input-number size="small" :min="0" :max="64"
                                   :controls="false"
                                   :model-value="selected.style?.radius"
                                   @update:model-value="setStyle('radius', $event)" />
                </div>
                <div class="style-field">
                  <span>{{ t("aedit.styleFontSize") }}</span>
                  <el-input-number size="small" :min="8" :max="48"
                                   :controls="false"
                                   :model-value="selected.style?.font_size"
                                   @update:model-value="setStyle('font_size', $event)" />
                </div>
              </div>
            </div>
          </div>
          <div v-show="configTab === 'interaction'" class="interaction-pane">
            <div class="visibility-box">
              <h4>{{ t("aedit.highlight") }}</h4>
              <el-select :model-value="selected.highlight_when?.param || ''"
                         clearable size="small" style="width: 100%"
                         :placeholder="t('aedit.visibilityNone')"
                         @update:model-value="setHighlightParam">
                <el-option v-for="p in currentPage.params || []"
                           :key="p.name" :value="p.name" :label="p.name" />
              </el-select>
              <div v-if="selected.highlight_when?.param" class="vis-row">
                <el-select v-model="selected.highlight_when.op" size="small"
                           style="width: 80px">
                  <el-option value="=" label="=" />
                  <el-option value="!=" label="!=" />
                  <el-option value="in" :label="t('aedit.visibilityIn')" />
                </el-select>
                <el-input v-model="highlightValueText" size="small"
                          :placeholder="t('aedit.visibilityValue')" />
                <el-select v-model="selected.highlight_when.tone" size="small"
                           style="width: 100px">
                  <el-option value="info" :label="t('aedit.toneInfo')" />
                  <el-option value="success" :label="t('aedit.toneSuccess')" />
                  <el-option value="warning" :label="t('aedit.toneWarning')" />
                  <el-option value="danger" :label="t('aedit.toneDanger')" />
                </el-select>
              </div>
              <p class="hint">{{ t("aedit.highlightHint") }}</p>
            </div>
            <template v-if="selected.type === 'button'">
              <div class="visibility-box">
                <h4>{{ t("aedit.actions") }}</h4>
                <template v-if="!selected.actions?.length">
                  <div class="field">
                    <span>{{ t("aedit.buttonTarget") }}</span>
                    <el-select v-model="selected.target_page" clearable
                               size="small" style="width: 100%">
                      <el-option v-for="p in content.pages" :key="p.id"
                                 :value="p.id" :label="p.title || p.id" />
                    </el-select>
                  </div>
                  <div class="field">
                    <span>{{ t("aedit.buttonUrl") }}</span>
                    <el-input v-model="selected.url" size="small"
                              placeholder="https://..." />
                  </div>
                  <el-button link size="small" @click="enableActions">
                    {{ t("aedit.useActions") }}
                  </el-button>
                </template>
                <template v-else>
                  <div class="action-list">
                    <div v-for="(action, i) in selected.actions" :key="i"
                         class="action-row">
                      <el-select v-model="action.type" size="small"
                                 style="width: 88px"
                                 @change="normalizeAction(action)">
                        <el-option value="navigate"
                                   :label="t('aedit.actNavigate')" />
                        <el-option value="url" :label="t('aedit.actUrl')" />
                        <el-option value="set_param"
                                   :label="t('aedit.actSetParam')" />
                        <el-option value="refresh"
                                   :label="t('aedit.actRefresh')" />
                        <el-option value="message"
                                   :label="t('aedit.actMessage')" />
                      </el-select>
                      <el-select v-if="action.type === 'navigate'"
                                 v-model="action.page" size="small"
                                 style="width: 90px">
                        <el-option v-for="p in content.pages" :key="p.id"
                                   :value="p.id" :label="p.title || p.id" />
                      </el-select>
                      <el-input v-else-if="action.type === 'url'"
                                v-model="action.url" size="small"
                                style="width: 110px" placeholder="/path" />
                      <template v-else-if="action.type === 'set_param'">
                        <el-select v-model="action.param" size="small"
                                   style="width: 78px">
                          <el-option v-for="p in currentPage.params || []"
                                     :key="p.name" :value="p.name"
                                     :label="p.name" />
                        </el-select>
                        <el-input v-model="action.value" size="small"
                                  style="width: 70px" />
                      </template>
                      <el-input v-else-if="action.type === 'message'"
                                v-model="action.text" size="small"
                                style="width: 120px"
                                :placeholder="t('aedit.actMessageText')" />
                      <el-button link type="danger" size="small"
                                 @click="selected.actions.splice(i, 1)"
                                 :aria-label="t('common.remove')">×</el-button>
                    </div>
                    <el-button link size="small" @click="addAction">
                      {{ t("aedit.addAction") }}
                    </el-button>
                  </div>
                  <el-button link size="small"
                             @click="selected.actions = undefined">
                    {{ t("aedit.useLegacy") }}
                  </el-button>
                </template>
              </div>
            </template>
          <div v-if="currentPage.params?.length" class="visibility-box">
            <h4>{{ t("aedit.visibility") }}</h4>
            <el-select :model-value="selected.visible_when?.param || ''"
                       clearable size="small" style="width: 100%"
                       :placeholder="t('aedit.visibilityNone')"
                       @update:model-value="setVisibleParam">
              <el-option v-for="p in currentPage.params" :key="p.name"
                         :value="p.name" :label="p.name" />
            </el-select>
            <div v-if="selected.visible_when?.param" class="vis-row">
              <el-select v-model="selected.visible_when.op" size="small"
                         style="width: 88px">
                <el-option value="=" label="=" />
                <el-option value="!=" label="!=" />
                <el-option value="in" :label="t('aedit.visibilityIn')" />
              </el-select>
              <el-input v-model="visibleValueText" size="small"
                        :placeholder="t('aedit.visibilityValue')" />
            </div>
            <p class="hint">{{ t("aedit.visibilityHint") }}</p>
          </div>
          <div class="visibility-box">
            <h4>{{ t("aedit.visibleRoles") }}</h4>
            <el-select :model-value="selected.visible_roles || []" multiple
                       clearable size="small" style="width: 100%"
                       :placeholder="t('aedit.visibleRolesAll')"
                       @update:model-value="setVisibleRoles">
              <el-option v-for="r in formRoles" :key="r" :value="r"
                         :label="t('role.' + r)" />
            </el-select>
            <p class="hint">{{ t("aedit.visibleRolesHint") }}</p>
          </div>
          </div>
          <p v-show="configTab === 'content'" class="hint">
            {{ t("aedit.configHint") }}
          </p>
        </template>
        <el-empty v-else :description="t('aedit.selectComponent')"
                  :image-size="60" />
      </aside>
    </div>

    <el-drawer v-model="versionsOpen" :title="t('aedit.versions')" size="480px"
               @open="loadVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" :label="t('aedit.version')" width="70" />
        <el-table-column prop="status" :label="t('aedit.status')" width="100" />
        <el-table-column prop="created_by" :label="t('aedit.createdBy')" />
        <el-table-column :label="t('aedit.actions')" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">
              {{ t("aedit.rollback") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <governance-drawer v-model="governanceOpen" :asset-id="id" />
    <el-drawer v-model="previewRowOpen" :title="t('acomp.detail')"
               size="420px">
      <el-descriptions :column="1" border>
        <el-descriptions-item v-for="(v, k) in previewRow" :key="k"
                              :label="k">{{ v }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import FavoriteButton from "../components/FavoriteButton.vue";
import AppCanvas from "../studio/app/AppCanvas.vue";
import { normalizeLayouts, nextLayout } from "../studio/app/bindings";
import { childListFor, findComponent, findRow, flatten,
         removeComponent as removeFromTree } from "../studio/app/tree";
import HistoryControls from "../components/HistoryControls.vue";
import { bindHistoryKeys, useHistory } from "../composables/useHistory";
import ShareDialog from "../studio/share/ShareDialog.vue";
import GovernanceDrawer from "../components/GovernanceDrawer.vue";
import { useDraftSafety } from "../draftSafety";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const draftVersion = ref(null);
const governanceOpen = ref(false);
const published = ref(false);
const content = ref({ start_page: "p1", pages: [] });
const history = useHistory(content);
const { canUndo, canRedo } = history;
bindHistoryKeys(history);
const currentId = ref("");
const selectedId = ref("");
const dragRow = ref(null);
const outlineQuery = ref("");
const addTarget = ref("page");
const configTab = ref("content");
const previewDevice = ref("desktop");
const previewRow = ref({});
const previewRowOpen = ref(false);
const previewComponents = reactive({});

function onPreviewComponentChange(componentId, values) {
  previewComponents[componentId] = {
    ...(previewComponents[componentId] || {}),
    values,
  };
}

function moveComponent(row, delta) {
  if (!row || !row.list) return;
  const index = row.list.indexOf(row.comp);
  const target = index + delta;
  if (index < 0 || target < 0 || target >= row.list.length) return;
  const [item] = row.list.splice(index, 1);
  row.list.splice(target, 0, item);
}

function dropComponent(row) {
  const source = dragRow.value;
  dragRow.value = null;
  if (!source || !row || source.list !== row.list
      || source.comp === row.comp) return;
  const from = source.list.indexOf(source.comp);
  const to = row.list.indexOf(row.comp);
  if (from < 0 || to < 0) return;
  const [item] = source.list.splice(from, 1);
  row.list.splice(to, 0, item);
}
const data = ref({});
const paramValues = ref({});
const loadingData = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const datasets = ref([]);
const metrics = ref([]);
const modelColumns = ref([]);
const paramTypes = ["string", "number", "date", "bool"];
const types = [
  { type: "text", labelKey: "aedit.compText" },
  { type: "heading", labelKey: "aedit.compHheading" },
  { type: "divider", labelKey: "aedit.compDivider" },
  { type: "image", labelKey: "aedit.compImage" },
  { type: "button", labelKey: "aedit.compButton" },
  { type: "progress", labelKey: "aedit.compProgress" },
  { type: "metric", labelKey: "aedit.compMetric" },
  { type: "table", labelKey: "aedit.compTable" },
  { type: "form", labelKey: "aedit.compForm" },
  { type: "container", labelKey: "aedit.compContainer" },
  { type: "tabs", labelKey: "aedit.compTabs" },
  { type: "modal", labelKey: "aedit.compModal" },
  { type: "upload", labelKey: "aedit.compUpload" },
  { type: "approval", labelKey: "aedit.compApproval" },
  { type: "list", labelKey: "aedit.compList" },
];
const configTabs = [
  { key: "content", label: "aedit.tabContent" },
  { key: "layout", label: "aedit.tabLayout" },
  { key: "interaction", label: "aedit.tabInteraction" },
];
const formWidgets = ["input", "textarea", "number", "date", "select",
                     "checkbox"];
const formRoles = ["viewer", "editor", "approver", "admin"];
const formColumns = ref([]);
const bindingPick = ref("");

const bindingOptions = computed(() => {
  const out = [];
  for (const param of currentPage.value?.params || []) {
    if (param.name) {
      out.push({ value: `params.${param.name}`,
                 label: `params.${param.name}` });
    }
  }
  for (const row of outlineRows.value) {
    const component = row.comp;
    if (component.type === "form") {
      for (const field of component.fields || []) {
        if (field.column) {
          out.push({
            value: `components.${component.id}.values.${field.column}`,
            label: `${component.title || component.id} · ${field.column}`,
          });
        }
      }
    }
    if (component.type === "upload") {
      for (const key of ["file.id", "file.name", "file.size", "file.url"]) {
        out.push({
          value: `components.${component.id}.values.${key}`,
          label: `${component.title || component.id} · ${key}`,
        });
      }
    }
    if (component.type === "table") {
      const cols = component.columns?.length ? component.columns
        : (data.value?.[component.id]?.columns || []);
      if (cols.length) {
        for (const column of cols) {
          out.push({
            value: `components.${component.id}.selectedRow.${column}`,
            label: `${component.title || component.id} · row.${column}`,
          });
        }
      } else {
        out.push({
          value: `components.${component.id}.selectedRow`,
          label: `${component.title || component.id} · selectedRow`,
        });
      }
    }
  }
  return out;
});

const currentPage = computed(() =>
  content.value.pages?.find((p) => p.id === currentId.value) || null);
const selected = computed(() =>
  currentPage.value ? findComponent(currentPage.value.components, selectedId.value)
    : null);
const outlineRows = computed(() => currentPage.value
  ? flatten(currentPage.value.components || []) : []);
const visibleOutline = computed(() => {
  const query = outlineQuery.value.trim().toLowerCase();
  if (!query) return outlineRows.value;
  const hit = (row) => [
    row.comp.id, row.comp.type, row.comp.title, row.comp.label,
    row.comp.text, typeLabel(row.comp.type),
  ].filter(Boolean).some((value) =>
    String(value).toLowerCase().includes(query));
  const shown = new Set();
  for (const row of outlineRows.value) {
    if (!hit(row)) continue;
    for (const id of row.path) shown.add(id);
  }
  return outlineRows.value.filter((row) => shown.has(row.comp.id));
});
const addTargets = computed(() => {
  const out = [{ value: "page", label: t("aedit.addToPage") }];
  for (const row of outlineRows.value) {
    const comp = row.comp;
    if (comp.type === "container" || comp.type === "modal") {
      out.push({
        value: `c:${comp.id}`,
        label: `${comp.title || typeLabel(comp.type)} · `
          + t("aedit.addToContainer"),
      });
    }
    if (comp.type === "tabs") {
      for (const tab of comp.tabs || []) {
        out.push({
          value: `t:${comp.id}:${tab.id}`,
          label: `${comp.title || comp.id} / ${tab.title || tab.id}`,
        });
      }
    }
  }
  return out;
});
const targetList = computed(() => {
  const value = addTarget.value;
  if (value.startsWith("c:")) {
    const comp = findComponent(currentPage.value?.components || [],
                               value.slice(2));
    return childListFor(comp);
  }
  if (value.startsWith("t:")) {
    const [, cid, tid] = value.split(":");
    const comp = findComponent(currentPage.value?.components || [], cid);
    return childListFor(comp, tid);
  }
  return currentPage.value?.components || null;
});
const listColumns = computed(() => {
  const c = selected.value;
  if (!c) return [];
  return data.value?.[c.id]?.columns || c.columns || [];
});

const columnsText = computed({
  get: () => (selected.value?.columns || []).join(", "),
  set: (v) => {
    if (selected.value) {
      selected.value.columns = String(v || "").split(",")
        .map((s) => s.trim()).filter(Boolean);
    }
  },
});

function typeLabel(type) {
  const found = types.find((x) => x.type === type);
  return found ? t(found.labelKey) : type;
}

function rowLabel(comp) {
  const fallback = typeLabel(comp.type);
  const title = comp.title?.trim();
  if (["text", "heading"].includes(comp.type)
      && (!title || title === fallback)) {
    const text = (comp.text || "").trim();
    if (text) return text.length > 24 ? `${text.slice(0, 24)}…` : text;
  }
  return title || comp.label || fallback;
}

function resetParams() {
  const values = {};
  for (const p of currentPage.value?.params || []) {
    if (!p.name) continue;
    values[p.name] = p.default ?? "";
  }
  paramValues.value = values;
}

async function load() {
  const a = await api.get(`/apps/${id}`);
  name.value = a.name;
  draftVersion.value = a.draft_version;
  published.value = Boolean(a.published_version);
  content.value = normalizeLayouts(a.draft || { start_page: "p1",
                                                  pages: [] });
  if (!content.value.pages?.length) {
    content.value = {
      start_page: "p1",
      pages: [{
        id: "p1", title: t("aedit.pageN"), params: [], components: [],
      }],
    };
  }
  if (!content.value.pages.some((p) => p.id === currentId.value)) {
    currentId.value = content.value.start_page
      || content.value.pages[0].id;
  }
  await loadOptions();
  resetParams();
  if (currentPage.value?.components.length) await refresh();
  await loadModel();
  history.reset();
  draftGuard.reset();
}

async function loadOptions() {
  const ds = (await api.get("/datasets?page_size=200")).items || [];
  const ms = (await api.get("/metrics?page_size=200")).items || [];
  datasets.value = ds.filter((d) => d.published);
  metrics.value = ms.filter((m) => m.published);
}

watch(currentId, async () => {
  selectedId.value = "";
  addTarget.value = "page";
  outlineQuery.value = "";
  resetParams();
  data.value = {};
  modelColumns.value = [];
  if (currentPage.value?.components.length) await refresh();
});

async function refresh() {
  if (!currentPage.value) return;
  loadingData.value = true;
  try {
    const r = await api.post(`/apps/${id}/data`, {
      page_id: currentPage.value.id,
      params: paramValues.value,
      limit: 100,
      content: content.value,
      design: true,
    });
    data.value = r.components || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loadingData.value = false;
  }
}

function addPage() {
  ElMessageBox.prompt(t("aedit.pageTitle"), t("aedit.newPage"), {
    inputPattern: /\S+/, inputErrorMessage: t("aedit.titleRequired"),
  }).then(({ value }) => {
    const pid = `p_${Date.now().toString(36)}`;
    content.value.pages.push({
      id: pid, title: value, params: [], components: [],
    });
    currentId.value = pid;
  }).catch(() => {});
}

async function removePage() {
  if (!currentPage.value || content.value.pages.length <= 1) return;
  try {
    await ElMessageBox.confirm(
      t("aedit.removePageConfirm")
        .replace("{title}", currentPage.value.title),
      t("aedit.deleteConfirm"));
    const pid = currentPage.value.id;
    content.value.pages = content.value.pages.filter((p) => p.id !== pid);
    if (content.value.start_page === pid) {
      content.value.start_page = content.value.pages[0].id;
    }
    currentId.value = content.value.pages[0].id;
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

function addParam() {
  if (!currentPage.value) return;
  const used = new Set((currentPage.value.params || [])
    .map((p) => p.name));
  let n = currentPage.value.params.length + 1;
  while (used.has(`p${n}`)) n += 1;
  currentPage.value.params = currentPage.value.params || [];
  currentPage.value.params.push({
    name: `p${n}`, type: "string", required: false,
    default: "", example: "",
  });
  resetParams();
}

function removeParam(i) {
  currentPage.value.params.splice(i, 1);
  resetParams();
}

async function addComponent(type) {
  const list = targetList.value;
  if (!currentPage.value || !list) return;
  const c = {
    id: `c_${Date.now().toString(36)}_${Math.random()
      .toString(36).slice(2, 5)}`,
    type,
    title: typeLabel(type),
    layout: nextLayout(list, type),
  };
  if (type === "text") c.text = t("aedit.defaultText");
  if (type === "heading") c.text = t("aedit.defaultHeading");
  if (type === "image") {
    c.url = "";
    c.alt = t("aedit.imageAlt");
  }
  if (type === "button") {
    c.label = t("acomp.open");
    c.target_page = "";
  }
  if (type === "progress") c.value = 50;
  if (type === "metric") {
    c.metric_id = metrics.value[0]?.id || null;
    c.value_column = "";
  }
  if (type === "table") {
    c.dataset_id = datasets.value[0]?.id || null;
    c.limit = 100;
    c.columns = [];
  }
  if (type === "form") {
    c.dataset_id = datasets.value[0]?.id || null;
    c.mode = "insert";
    c.key = "";
    c.fields = [];
    c.submit_text = t("aedit.submit");
    c.success_message = t("aedit.submitSuccess");
  }
  if (type === "container") c.children = [];
  if (type === "modal") {
    c.children = [];
    c.label = t("aedit.modalOpen");
    c.title = t("aedit.modalTitle");
  }
  if (type === "tabs") {
    c.tabs = [{ id: "t1", title: t("aedit.tabN"), components: [] }];
  }
  if (type === "upload") {
    c.label = t("aedit.uploadLabel");
    c.accept = ["csv", "xlsx", "pdf"];
    c.max_mb = 20;
  }
  if (type === "approval") {
    c.title = t("aedit.approvalTitle");
    c.limit = 10;
  }
  if (type === "list") {
    c.dataset_id = datasets.value[0]?.id || null;
    c.limit = 100;
    c.columns = [];
    c.title_column = "";
    c.subtitle_column = "";
    c.value_column = "";
  }
  list.push(c);
  selectedId.value = c.id;
  if (type === "metric") await loadModel();
  if (type === "table" && c.dataset_id) await chooseDataset(c.dataset_id);
  if (type === "form" && c.dataset_id) await loadFormSchema(c.dataset_id);
  await refresh();
}

function onCanvasChangeEnd() {
  history.commit();
  history.resume();
}

function navigatePreview(pageId) {
  if (content.value.pages.some((p) => p.id === pageId)) {
    currentId.value = pageId;
  }
}

function openPreviewRow(payload) {
  const row = payload?.row || payload || {};
  if (payload?.componentId) {
    previewComponents[payload.componentId] = {
      ...(previewComponents[payload.componentId] || {}),
      selectedRow: row,
    };
  }
  previewRow.value = row;
  previewRowOpen.value = true;
}

function autoLayout() {
  layoutList(currentPage.value?.components || []);
  history.commit();
}

function layoutList(list) {
  let y = 0;
  for (const c of list) {
    const size = nextLayout([], c.type);
    c.layout = { ...size, y };
    y += size.h;
    if (c.type === "container" || c.type === "modal") {
      layoutList(c.children || []);
    } else if (c.type === "tabs") {
      for (const tab of c.tabs || []) layoutList(tab.components || []);
    }
  }
}

function insertBinding() {
  if (!selected.value || !bindingPick.value) return;
  const token = `{{${bindingPick.value}}}`;
  selected.value.text = `${selected.value.text || ""}${token}`;
  bindingPick.value = "";
}

function setAccept(text) {
  if (!selected.value) return;
  selected.value.accept = String(text || "").split(",")
    .map((item) => item.trim().replace(/^\./, ""))
    .filter(Boolean).slice(0, 10);
}

function setPageRoles(roles) {
  if (!currentPage.value) return;
  currentPage.value.visible_roles = roles?.length ? roles : undefined;
}

function setStyle(key, value) {
  if (!selected.value) return;
  if (value === null || value === undefined || value === "") {
    if (selected.value.style) {
      delete selected.value.style[key];
      if (!Object.keys(selected.value.style).length) {
        selected.value.style = undefined;
      }
    }
    return;
  }
  selected.value.style = { ...(selected.value.style || {}), [key]: value };
}

function setHighlightParam(name) {
  if (!selected.value) return;
  if (!name) {
    delete selected.value.highlight_when;
    return;
  }
  selected.value.highlight_when = {
    param: name,
    op: selected.value.highlight_when?.op || "=",
    value: selected.value.highlight_when?.value ?? "",
    tone: selected.value.highlight_when?.tone || "info",
  };
}

const highlightValueText = computed({
  get: () => {
    const value = selected.value?.highlight_when?.value;
    return Array.isArray(value) ? value.join(",") : (value ?? "");
  },
  set: (text) => {
    const rule = selected.value?.highlight_when;
    if (!rule) return;
    rule.value = rule.op === "in"
      ? String(text || "").split(",").map((x) => x.trim()).filter(Boolean)
      : text;
  },
});

function setVisibleRoles(roles) {
  if (!selected.value) return;
  selected.value.visible_roles = roles?.length ? roles : undefined;
}

function enableActions() {
  if (!selected.value) return;
  selected.value.actions = [];
  selected.value.target_page = "";
  selected.value.url = "";
  addAction();
}

function addAction() {
  if (!selected.value) return;
  selected.value.actions = selected.value.actions || [];
  selected.value.actions.push({
    type: "navigate", page: content.value.pages[0]?.id || "",
  });
}

function addTab(comp) {
  const tabs = comp.tabs || (comp.tabs = []);
  let n = tabs.length + 1;
  const used = new Set(tabs.map((tab) => tab.id));
  while (used.has(`t${n}`)) n += 1;
  tabs.push({ id: `t${n}`, title: `${t("aedit.tabN")} ${n}`,
              components: [] });
}

function removeTab(comp, index) {
  if (!comp.tabs || comp.tabs.length <= 1) return;
  comp.tabs.splice(index, 1);
}

function normalizeAction(action) {
  if (action.type === "navigate") {
    action.page = action.page || content.value.pages[0]?.id || "";
  } else if (action.type === "url") {
    action.url = action.url || "";
  } else if (action.type === "set_param") {
    action.param = action.param
      || (currentPage.value?.params || [])[0]?.name || "";
    action.value = action.value ?? "";
  } else if (action.type === "message") {
    action.text = action.text || "";
  }
}

function setVisibleParam(name) {
  if (!selected.value) return;
  if (!name) {
    delete selected.value.visible_when;
    return;
  }
  selected.value.visible_when = {
    param: name,
    op: selected.value.visible_when?.op || "=",
    value: selected.value.visible_when?.value ?? "",
  };
}

const visibleValueText = computed({
  get: () => {
    const value = selected.value?.visible_when?.value;
    return Array.isArray(value) ? value.join(",") : (value ?? "");
  },
  set: (text) => {
    const rule = selected.value?.visible_when;
    if (!rule) return;
    rule.value = rule.op === "in"
      ? String(text || "").split(",").map((x) => x.trim()).filter(Boolean)
      : text;
  },
});

function selectComponent(cid) {
  selectedId.value = cid;
  loadModel();
  if (selected.value?.type === "form" && selected.value.dataset_id) {
    loadFormSchema(selected.value.dataset_id);
  }
}

function removeComponent() {
  if (!selected.value) return;
  const cid = selected.value.id;
  removeFromTree(currentPage.value.components, cid);
  delete data.value[cid];
  selectedId.value = "";
  if (addTarget.value.includes(cid)) addTarget.value = "page";
  modelColumns.value = [];
}

async function loadModel() {
  modelColumns.value = [];
  const c = selected.value;
  if (!c || !c.metric_id) return;
  try {
    const m = await api.get(`/metrics/${c.metric_id}`);
    const mc = m.published || m.draft || {};
    const dims = [...(mc.dimensions || [])];
    if (mc.time?.column && !dims.includes(mc.time.column)) {
      dims.push(mc.time.column);
    }
    const alias = (mc.measure || {}).as || "value";
    const cols = [...dims, alias];
    modelColumns.value = cols;
    if (!c.value_column || !cols.includes(c.value_column)) {
      c.value_column = alias;
    }
    if (c.type === "table") {
      c.columns = (c.columns || []).filter((x) => cols.includes(x));
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function selectDataset(datasetId) {
  await chooseDataset(datasetId);
  await refresh();
}

async function selectMetric(metricId) {
  if (selected.value) selected.value.dataset_id = null;
  await loadModel();
  await refresh();
}

async function chooseDataset(datasetId) {
  const c = selected.value;
  if (!c || !datasetId) return;
  c.metric_id = null;
  try {
    const d = await api.get(`/datasets/${datasetId}`);
    const dc = d.published || d.draft || {};
    const cols = (dc.query?.select || [])
      .map((s) => s.as || s.column);
    c.columns = (c.columns || []).filter((x) => cols.includes(x));
    if (!currentPage.value.params) currentPage.value.params = [];
    for (const p of dc.params || []) {
      if (!p.name) continue;
      if (!currentPage.value.params.some((x) => x.name === p.name)) {
        currentPage.value.params.push({
          name: p.name, type: p.type || "string",
          required: Boolean(p.required),
          default: p.default ?? "", example: p.example ?? "",
        });
      }
    }
    resetParams();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadFormSchema(datasetId, prune = false) {
  if (!datasetId) {
    formColumns.value = [];
    return;
  }
  try {
    const r = await api.get(
      `/apps/${id}/form-schema?dataset_id=${encodeURIComponent(datasetId)}`);
    formColumns.value = r.columns || [];
    if (prune && selected.value?.type === "form") {
      selected.value.fields = (selected.value.fields || [])
        .filter((f) => formColumns.value.includes(f.column));
    }
  } catch (e) {
    formColumns.value = [];
    ElMessage.error(errMsg(e));
  }
}

async function selectFormDataset(datasetId) {
  await loadFormSchema(datasetId, true);
  const c = selected.value;
  if (c && c.key && !formColumns.value.includes(c.key)) c.key = "";
  if (c?.mode === "delete") onFormModeChange("delete");
}

function setRoles(v) {
  if (selected.value) {
    selected.value.allow_roles = v?.length ? v : undefined;
  }
}

function onFormModeChange(mode) {
  const c = selected.value;
  if (!c || mode !== "delete") return;
  const key = c.key && formColumns.value.includes(c.key)
    ? c.key : (formColumns.value[0] || "");
  c.key = key;
  c.fields = c.fields || [];
  if (key && !c.fields.some((f) => f.column === key)) {
    c.fields.push({ column: key, label: "", widget: "input",
                    required: true });
  }
}

function addField() {
  if (!selected.value) return;
  selected.value.fields = selected.value.fields || [];
  selected.value.fields.push({
    column: formColumns.value[0] || "",
    label: "",
    widget: "input",
    required: false,
  });
}

function removeField(i) {
  selected.value.fields.splice(i, 1);
}

function setOptions(field, text) {
  field.options = String(text || "").split(",")
    .map((x) => x.trim()).filter(Boolean);
}

async function submitForm(componentId, values) {
  if (!(await save())) throw new Error(t("aedit.saveFirst"));
  await api.post(`/apps/${id}/submit`, {
    component_id: componentId,
    values,
  });
  await refresh();
}

async function save(silent = false) {
  try {
    const body = { content: content.value };
    if (draftVersion.value !== null) body.base_version = draftVersion.value;
    const result = await api.put(`/apps/${id}/draft`, body);
    draftVersion.value = result.version;
    if (!silent) ElMessage.success(t("aedit.savedDraft"));
    return true;
  } catch (e) {
    if (/draft changed/i.test(e.message || "")) {
      ElMessageBox.confirm(t("draft.conflict"), t("draft.conflictTitle"),
        { type: "warning" })
        .then(() => load()).catch(() => {});
    } else if (!silent) {
      ElMessage.error(errMsg(e));
    }
    return false;
  }
}

const draftGuard = useDraftSafety({ content, save });

async function rename() {
  try {
    await api.put(`/apps/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/apps/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success(t("aedit.validatePassed"));
    else ElMessage.error(r.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish() {
  const ok = await save();
  if (!ok) return;
  try {
    await api.applyChange("publish_app", id);
    await load();
    ElMessage.success(t("aedit.published"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/apps/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      t("aedit.rollbackConfirm").replace("{version}", row.version),
      t("aedit.rollbackTitle"));
    await api.applyChange("rollback_app", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.app-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
            background: #f8fafc; border: 1px solid #e5e7eb;
            border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 280px 1fr 320px;
        min-height: 0; }
.left { background: #fff; border-right: 1px solid #e5e7eb; overflow: auto;
        padding: 10px; }
.section { margin-bottom: 16px; }
.section-head { display: flex; justify-content: space-between;
                align-items: center; font-size: 12px; font-weight: 600;
                color: #334155; margin-bottom: 6px; }
.pages { display: flex; flex-direction: column; gap: 3px; }
.page-row { display: flex; justify-content: space-between; align-items: center;
            padding: 6px 8px; border-radius: 6px; cursor: pointer;
            font-size: 12px; color: #475569; }
.page-row:hover { background: #f1f5f9; }
.page-row.active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.page-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-actions { display: flex; gap: 4px; align-items: center; margin-top: 6px;
                flex-wrap: wrap; }
.param { display: flex; gap: 3px; align-items: center; margin-bottom: 4px;
         flex-wrap: wrap; }
.param :deep(.el-input) { width: 74px; }
.palette { display: flex; flex-direction: column; gap: 4px; }
.palette .add { width: 100%; margin: 0; }
.add-target { display: flex; align-items: center; gap: 6px; margin-top: 8px;
              font-size: 11px; color: #475569; }
.outline-search { margin-top: 8px; }
.components { margin-top: 8px; display: flex; flex-direction: column; gap: 2px; }
.comp-row { display: flex; align-items: center; gap: 8px;
            padding: 6px 8px; border-radius: 6px; cursor: grab;
            font-size: 12px; color: #475569; }
.comp-row.dragging { opacity: 0.5; }
.comp-row.nested { background: #fafbfc; }
.comp-row.nested .comp-name { font-weight: 400; }
.comp-name { flex: 1; min-width: 0; overflow: hidden;
             text-overflow: ellipsis; white-space: nowrap; }
.drag-handle { color: #cbd5e1; font-size: 11px; letter-spacing: -1px; }
.comp-actions { display: inline-flex; opacity: 0; }
.comp-row:hover .comp-actions, .comp-row.active .comp-actions {
  opacity: 1;
}
.comp-row:hover { background: #f1f5f9; }
.comp-row.active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.comp-type { color: #6b7280; font-size: 11px; }
.hint { color: #6b7280; font-size: 11px; margin: 8px 0 0; }
.canvas { overflow: auto; padding: 14px; }
.canvas-toolbar { display: flex; justify-content: flex-end; margin-bottom: 8px; }
.canvas-frame { width: 100%; transition: max-width 0.2s ease; }
.canvas-frame.tablet { max-width: 680px; margin: 0 auto;
                       border: 1px solid #e5e7eb; border-radius: 8px;
                       padding: 10px; background: #fff; }
.preview-filters { display: flex; gap: 10px; align-items: flex-end;
                   flex-wrap: wrap; margin-bottom: 10px; padding: 8px 10px;
                   background: #fff; border: 1px solid #e5e7eb;
                   border-radius: 6px; }
.filter { display: flex; flex-direction: column; gap: 3px;
          font-size: 11px; color: #475569; }
.layout-box, .visibility-box { border-top: 1px solid #eef2f7;
                               margin-top: 10px; padding-top: 10px; }
.layout-grid { display: grid; grid-template-columns: repeat(4, 1fr);
               gap: 4px; }
.layout-grid :deep(.el-input-number) { width: 100%; }
.vis-row { display: flex; gap: 6px; margin-top: 6px; }
.binding-row { display: flex; gap: 6px; width: 100%; }
.action-list { display: flex; flex-direction: column; gap: 5px; width: 100%; }
.action-row { display: flex; gap: 4px; align-items: center;
              flex-wrap: wrap; }
.visibility-box + .visibility-box { margin-top: 6px; }
.tab-list { display: flex; flex-direction: column; gap: 4px; width: 100%; }
.tab-row { display: flex; gap: 4px; align-items: center; }
.config { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto;
          padding: 12px; }
.config-head { display: flex; justify-content: space-between; align-items: center; }
.config-tabs { display: flex; gap: 4px; margin: 10px 0 4px;
               border-bottom: 1px solid #eef2f7; }
.config-tab { border: 0; background: transparent; padding: 5px 8px;
              font-size: 12px; color: #64748b; cursor: pointer;
              border-bottom: 2px solid transparent; }
.config-tab.active { color: #1d4ed8; border-bottom-color: #1d4ed8;
                     font-weight: 600; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 11px;
         color: #475569; margin-bottom: 8px; }
.style-box { border-top: 1px solid #eef2f7; margin-top: 10px; padding-top: 10px; }
.style-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.style-field { display: flex; flex-direction: column; gap: 4px;
               font-size: 11px; color: #475569; }
.style-field :deep(.el-select), .style-field :deep(.el-input-number) {
  width: 100%;
}
h4 { margin: 0 0 12px; font-size: 13px; }
</style>
