# Ghi chú tính năng (cho phát triển — KHÔNG hiện cho khách)

User 15/10: "rút ngắn lại tất cả các phần giải thích này về thành mô tả ngắn tính năng chính đó làm gì. không cần show cả quy trình, việc thông tin cả quy trình lưu lại để phục vụ việc phát triển thôi". Mỗi mục: chỗ trong mã, câu ngắn đang hiện, rồi bản giải thích đầy đủ cũ.

## Rút gọn 15/10/2026

### (gợi ý) — `autotone_gui.py` (dòng ~2566)

**Hiện:** Chọn loại buổi chụp — đặt sẵn mức sáng và màu phù hợp.

**Đầy đủ:**

> Cưới: không bù. Sự kiện: bù sáng {} EV cho cả buổi. Kỷ yếu: bù sáng {} EV, tone nền sáng trong — trung tính sáng hơn, đen sâu hơn, vùng sáng nén lại (khi preset để trống Tone); không tự mở vùng tối; phanh chống cháy da nhường để mặt lên mức sáng chuẩn (tối đa +{} EV); cân trắng ấm/hồng nhẹ (+{} K, Tint +{}); cảnh đèn vàng nặng (cân trắng kéo lạnh gần hết mức) sáng thêm +{} EV; KHÔNG chỉnh HSL (giữ HSL của preset; ảnh tool từng chỉnh HSL được trả về số preset). Không tự bật Color Grading (nó ám màu cả khung). Chọn xong vẫn sửa được số ở thanh dưới.

### (gợi ý) — `autotone_gui.py` (dòng ~2594)

**Hiện:** Tăng / giảm sáng cho cả buổi (EV).

**Đầy đủ:**

> Bù sáng cả buổi — EV, cộng sau chống cháy. Cưới 0 · Sự kiện {}. Ảnh không có mặt giữ nguyên. Mốc sáng mặt: {} EV.

### (gợi ý) — `autotone_gui.py` (dòng ~2604)

**Hiện:** Ấm / lạnh hơn cho cả buổi (K). Dương = ấm hơn, âm = lạnh hơn.

**Đầy đủ:**

> Bù nhiệt độ cả buổi (K): cộng vào Temperature của mọi ảnh SAU mọi bước cân WB tự động (kể cả “Ngoài trời buổi tối”). Dương = ấm hơn, âm = lạnh hơn. Ảnh đen trắng giữ nguyên; Cân bằng trắng “Không đụng tới” thì không áp.

### (gợi ý) — `autotone_gui.py` (dòng ~2611)

**Hiện:** Chỉnh Tint cho cả buổi. Dương = hồng hơn, âm = xanh lá hơn.

**Đầy đủ:**

> Bù Tint cả buổi: cộng vào Tint của mọi ảnh như Bù K. Dương = hồng / magenta hơn, âm = xanh lá hơn.

### Ngoài trời buổi tối: giữ ấm, không kéo lạnh — `autotone_gui.py` (dòng ~2657)

**Hiện:** Ảnh ngoài trời chụp từ 17h: giữ không khí ấm của đèn, không kéo lạnh.

**Đầy đủ:**

> Tự nhận cảnh ngoài trời (cây, trời, phố) hay trong nhà (tường, trần, hội trường) bằng mô hình Places365, gộp theo 30 phút. Ảnh ngoài trời chụp từ 17h, trời tối: dùng màu da ánh sáng ngày và KHÔNG hạ nhiệt độ màu dưới preset — đèn LED / flash gel cam là không khí của buổi. Chọn “Ánh đèn” ở trên thì không áp.

### Chế độ — `autotone_gui.py` (dòng ~2665)

**Hiện:** Đưa mặt về mức sáng chuẩn (khuyên dùng): mọi ảnh có mặt cùng một mức sáng da.
Cân trong từng cảnh / cả buổi: theo độ sáng trung bình.
Trộn: pha giữa hai cách.

**Đầy đủ:**

> Đưa mặt về mức sáng chuẩn: mọi ảnh có mặt đưa về cùng một mức sáng da ({} EV) — khuyên dùng.
> Cân trong từng cảnh: theo trung vị độ sáng của chính cảnh đó.
> Cân cả buổi về một mức: trung vị của cả buổi.
> Trộn: pha giữa trung vị cảnh và mức chuẩn (ô “Độ trộn”).

### Đo sáng — `autotone_gui.py` (dòng ~2673)

**Hiện:** Vùng dùng để đo độ sáng. “Khuôn mặt + điểm bắt nét” là khuyên dùng.

**Đầy đủ:**

> Đo độ sáng ở đâu trên ảnh. “Khuôn mặt + điểm bắt nét” đo da mặt của người được lấy nét — khuyên dùng. Đổi cách đo thì bấm “Xử lý ảnh” để đo lại ảnh.

### Ảnh nhiều người: đo mặt nét sáng nhất — `autotone_gui.py` (dòng ~2681)

**Hiện:** Ảnh nhóm: đo theo mặt nét và sáng nhất để không ai bị cháy.

**Đầy đủ:**

> Ảnh có từ 2 mặt: bỏ mặt out nét, đo theo mặt đang được chiếu sáng nhất — mặt đó không bị cháy, cả nhóm cùng một mức. Ảnh đám đông không tối đi quá 0.5 EV so với cách đo cũ. Ảnh một người giữ nguyên.

### Cân bằng trắng — `autotone_gui.py` (dòng ~2686)

**Hiện:** Da trắng hồng: đưa màu da về màu đích.
Theo nhiệt độ máy: giữ WB của máy ảnh.
Grey-world: cân theo màu trung bình của ảnh.

**Đầy đủ:**

> Da trắng hồng: kéo màu da về đích da trắng hồng (đích riêng cho ánh sáng ngày và ánh đèn), kèm WB người chụp đặt trên máy khi preset để trống WB.
> Theo nhiệt độ máy đo được: chỉ kéo về WB của máy.
> Grey-world: cân theo màu trung bình của preview.

### (gợi ý) — `autotone_gui.py` (dòng ~2706)

**Hiện:** Màu da mà tool đưa về. “Tạo từ ảnh đã sửa…” để lấy màu da theo gu của bạn.

**Đầy đủ:**

> MÀU DA ĐÍCH — màu da mà Cân bằng trắng, HSL da và Color Grading cùng nhắm tới. Hai chấm: đích ánh đèn · đích ánh sáng ngày. Mặc định: da trắng hồng (đèn) và da rám (ngày).
> “Màu da › Tạo từ ảnh đã sửa…”: chọn vài ảnh JPEG bạn đã chỉnh xong theo gu của mình (xuất từ Lightroom). Tool đo da trên các mặt trong ảnh — cùng cách đo với ảnh RAW — tách theo ánh sáng ngày / đèn (EXIF), lưu thành mẫu có tên. App nhớ mẫu dùng gần nhất và mẫu riêng của từng buổi.

### Chế độ nhanh một lượt (thử nghiệm) — `autotone_gui.py` (dòng ~2715)

**Hiện:** Tính màu da một lần trên preview Lightroom — nhanh hơn. Cần học màu Lightroom cho máy ảnh (⋯ › Học màu Lightroom…).

**Đầy đủ:**

> Đo da trên preview Lightroom rồi tính WB / HSL / Color Grading một lần cho trúng màu da đích — nhanh hơn đường thường (đo trên buổi thật: 15 → 6 phút). Cần mô hình màu Lightroom của máy ảnh: bộ cài có sẵn Sony A7 IV, A7 V, Nikon Z5 II, Z 8; máy khác học ở ⋯ › Học màu Lightroom cho máy ảnh này…. Máy chưa có mô hình tự đi đường thường.

### Mặt sáng tới mức — `autotone_gui.py` (dòng ~2724)

**Hiện:** Mức sáng đích của da mặt (EV).

**Đầy đủ:**

> Mức sáng ĐÍCH của da mặt (EV log2, càng âm càng tối). Mặc định {}. Chỉ dùng ở chế độ “Đưa mặt về mức sáng chuẩn” và “Trộn”.

### Dìm tối đa − — `autotone_gui.py` (dòng ~2743)

**Hiện:** Mức giảm sáng tối đa cho mỗi ảnh (EV).

**Đầy đủ:**

> Trần cho chiều DÌM TỐI. Đo ra phải dìm 1.8 EV mà đặt 1.00 thì chỉ dìm 1.00. Chiều kéo sáng do ô dưới quyết định.

### Kéo sáng tối đa + — `autotone_gui.py` (dòng ~2746)

**Hiện:** Mức tăng sáng tối đa cho mỗi ảnh (EV).

**Đầy đủ:**

> Trần cho chiều KÉO SÁNG, để riêng vì hai chiều không đối xứng: dìm quá tay chỉ mất công, kéo sáng thì cứu được ảnh ngược sáng hay chụp trước màn LED. Phần chống cháy sáng vẫn gác.

### Mức độ can thiệp — `autotone_gui.py` (dòng ~2750)

**Hiện:** Độ mạnh của chỉnh sáng: 1.0 = đủ, nhỏ hơn = nhẹ tay, lớn hơn = mạnh tay.

**Đầy đủ:**

> Nhân vào mức chỉnh trước khi kẹp trần. 1.0 = đủ như đo được, 0.7 = dè dặt, 1.2 = mạnh tay.

### Tự kéo Shadows khi bết tối — `autotone_gui.py` (dòng ~2761)

**Hiện:** Mở vùng tối khi ảnh bị bết.

**Đầy đủ:**

> Nâng Shadows khi vùng tối bết lại; chỉ cộng lên số của preset.
> Loại buổi Kỷ yếu thì không mở (giữ đen sâu như ảnh kỷ yếu đã duyệt).

### Tự chỉnh HSL màu da (Cưới) — `autotone_gui.py` (dòng ~2769)

**Hiện:** Chỉnh HSL kênh Cam để da về đúng màu đích.

**Đầy đủ:**

> Đã chọn MẪU Màu da (mọi loại buổi): kênh Cam đưa da về đúng màu da của mẫu — một đích cho cả WB, HSL và Color Grading; da đo trên ảnh duyệt, chưa có thì dự đoán; chạm trần vẫn áp phần làm da gần mẫu hơn.
> Kênh Cam (Orange) đưa da chủ thể về TRẮNG, chỉ hơi hồng — CHỈ khi đã ĐO được da thật sau WB + Tone:
> 1. Ghi (WB + Tone).  2. ⋯ → Duyệt nhanh → Dựng ảnh duyệt.  3. Ghi lại: tool đo da trên ảnh duyệt Lightroom vẽ rồi mới quyết HSL.  4. Duyệt lại để kiểm.
> · Độ đậm da về {}–{} (trắng hơn preset ~0.046); hue {}–{}°: vàng hơn thì kéo bớt vàng tới mép, đỏ hơn thì lùi về vàng; da trong khoảng thì không đụng. Theo từng cảnh.
> · Tính từ màu da của PRESET GỐC (trừ phần HSL tool đã ghi) — phần chỉnh trước tự được gỡ, Ghi nhiều lần không cộng dồn.
> · KHÔNG đổi cân trắng. Chỉ preset SAY (saymedia7v / NoWBExposure); tắt ô thì ảnh tool đã chỉnh HSL trả về số preset.

### Đẩy tone về da trắng hồng — `autotone_gui.py` (dòng ~2786)

**Hiện:** Dùng Color Grading đưa da về trắng hồng khi HSL chưa đủ. Có thể làm ám màu cả khung.

**Đầy đủ:**

> Đã chọn MẪU Màu da: Color Grading xoay phần da CÒN lệch mẫu sau HSL, không đẩy vùng trắng quá 0.003 OkLab (không ám).
> Color Grading về da trắng hồng (da đào) như ảnh kỷ yếu anh đã duyệt — bước CUỐI của chuỗi màu da: cân WB + Tone → đo màu da dự đoán trong Lightroom → HSL kênh da (Kỷ yếu) → đo lại → Color Grading chỉ cho ảnh da CÒN lệch quá {}°, tính trên phần vượt, trần Sat {}.
> · Lưu ý: Color Grading đổi màu cả các vùng cam / trắng trong khung, dễ thấy ám màu — nên để TẮT trừ khi HSL chưa đủ.
> · Kỷ yếu: bật / tắt ô này KHÔNG đổi cân trắng và HSL. Cưới / Sự kiện: bật thì cân trắng đưa da về màu học từ ảnh kỷ yếu (riêng trong nhà và ngoài trời).
> · Cộng vào bánh xe Midtone + Highlight của preset, không ghi đè. Tắt lại thì ảnh tool đã grade được trả về số của preset. Ảnh không thấy mặt thì không grade.

### Tự chỉnh Curve (parametric) — `autotone_gui.py` (dòng ~2802)

**Hiện:** Chỉnh 4 vùng sáng của Tone Curve (Highlights / Lights / Darks / Shadows), cộng lên preset.

**Đầy đủ:**

> Cộng bốn núi parametric curve (Highlights / Lights / Darks / Shadows) lên preset; point curve của preset giữ nguyên.

### Curve R/G/B: da mặt về màu đích — `autotone_gui.py` (dòng ~2807)

**Hiện:** Chỉnh curve R / G / B để da mặt về đúng màu đích.

**Đầy đủ:**

> Sau khi áp WB / Tone, Lightroom dựng lại ảnh, app tách mặt nạ da mặt và đo TỪNG điểm da, rồi chỉnh ba kênh R / G / B của curve để da về màu đích (mẫu màu da nếu có). Ghép vào curve của preset, không ghi đè.
> · Chỉ chỉnh dải sáng của da; vùng trắng / xám cùng độ sáng không được ám quá 0,003 (OkLab) — vượt thì thu bớt.
> · Không tới được đích thì vẫn chỉnh phần làm da gần đích hơn (không đổi xấu hue để được chroma hay ngược lại).
> · Cả loạt ảnh liền nhau cùng một curve. Cần nguồn catalog và plugin bản mới; thêm ~7–10 phút / 1000 ảnh.

### Curve tổng: nén vùng cháy sáng — `autotone_gui.py` (dòng ~2817)

**Hiện:** Hạ vùng sáng nhất của curve khi ảnh bị cháy.

**Đầy đủ:**

> Sau khi áp WB / Tone, ảnh Lightroom dựng còn cháy (≥ 2% khung có kênh ≥ 250, đã bỏ đốm bóng) thì bẻ ĐỈNH curve tổng: dưới mức sáng của da giữ nguyên, phần sáng nhất hạ xuống (đỉnh không dưới 235).
> · Chỗ đã cháy hẳn trong RAW không lấy lại được chi tiết — thành trắng xám phẳng.
> · Cả loạt ảnh liền nhau cùng một mức nén.

### Nghỉ quá (phút) — `autotone_gui.py` (dòng ~2837)

**Hiện:** Hai ảnh cách nhau quá số phút này thì tính là cảnh mới.

**Đầy đủ:**

> Nghỉ giữa hai tấm quá số phút này thì coi là cảnh mới. Thanh kéo 1–60; cần hơn thì gõ thẳng vào ô số (tới 240).

### Tách cảnh theo bối cảnh khung hình — `autotone_gui.py` (dòng ~2847)

**Hiện:** Đổi phông hoặc chỗ đứng thì tính là cảnh mới.

**Đầy đủ:**

> So chữ ký bố cục của từng khung; đổi phông / đổi chỗ đứng thì sang cảnh mới dù chụp liền tay.

### Gom cảnh theo từng máy (xếp theo tên file) — `autotone_gui.py` (dòng ~2852)

**Hiện:** Buổi nhiều máy: gom cảnh riêng cho từng máy.

**Đầy đủ:**

> Buổi nhiều máy chụp cùng lúc: ảnh mỗi máy xếp theo tên file và gom cảnh riêng — ảnh máy này không chen vào cảnh của máy kia làm vụn cảnh. Lưới ảnh cũng hiện theo thứ tự đó.

### Đồng bộ sáng + màu trong cùng bối cảnh — `autotone_gui.py` (dòng ~2856)

**Hiện:** Các ảnh trong cùng cảnh có cùng độ sáng và màu.

**Đầy đủ:**

> Trong một cảnh, đưa mọi tấm về cùng độ sáng và màu SAU chỉnh — xem liền một dải ảnh không bị nhấp nháy.

### Cùng khung + cùng thông số → cùng một mức — `autotone_gui.py` (dòng ~2861)

**Hiện:** Loạt ảnh chụp liền tay cùng thông số nhận cùng một mức sáng và màu.

**Đầy đủ:**

> Loạt chụp liền tay (cùng máy, cùng khẩu/tốc/ISO, cùng bố cục, trong 60 giây) nhận đúng MỘT mức sáng và màu.

### Cùng chủ thể trong chuỗi ảnh liền → da đều nhau — `autotone_gui.py` (dòng ~2866)

**Hiện:** Chuỗi ảnh cùng một người: da đều nhau giữa các tấm.

**Đầy đủ:**

> Chuỗi ảnh liền nhau (cùng máy, cùng thông số, cách ≤ 15 giây) mà máy lấy nét vào cùng người: đo da người đó ở từng tấm rồi chỉnh để da ra đều nhau — người đi lại gần đèn sáng dần lên thì Exposure giảm dần theo.

### Lọc ảnh trùng khung — `autotone_gui.py` (dòng ~2890)

**Hiện:** Loạt ảnh chụp liên tiếp: tấm có người nhắm mắt được gắn 1 sao.

**Đầy đủ:**

> Chụp liên tiếp: ảnh 1–4 người CÓ NGƯỜI NHẮM MẮT → 1 sao; ai cũng mở mắt thì giữ; ảnh trên 4 người giữ nguyên. Đo mắt khi phân tích (~0.8s/ảnh)

### Lọc ảnh mắt không dùng được — `autotone_gui.py` (dòng ~2893)

**Hiện:** Gắn 1 sao cho ảnh có người nhắm mắt (ảnh 1–4 người).

**Đầy đủ:**

> 1 người hoặc nhóm 2–4; ảnh tập thể đông người bỏ qua. Chỉ xét mặt trực diện / 3/4 — mặt nghiêng bỏ qua. Đo luôn khi phân tích, chậm thêm ~0.8s/ảnh

### Auto Transform cho ảnh backdrop / màn LED — `autotone_gui.py` (dòng ~2898)

**Hiện:** Tự chỉnh thẳng (Upright Auto) cho ảnh chụp trước backdrop / màn LED.

**Đầy đủ:**

> Ghi Upright = Auto cho ảnh nhiều đường thẳng (backdrop, màn LED) có người mà mặt không chiếm quá lớn.

### Áp cả ảnh Loại 1★ vào Lightroom — `autotone_gui.py` (dòng ~2903)

**Hiện:** Bật: áp cho mọi ảnh, ảnh Loại gắn 1★. Tắt: chỉ áp ảnh Giữ.

**Đầy đủ:**

> Bật: Xử lý ảnh áp thông số cho MỌI ảnh, ảnh Loại được gắn 1★ để lọc bên Lightroom. Tắt: chỉ áp ảnh Giữ — ảnh Loại không đổi thông số, không gắn sao.

### Denoise ảnh ISO cao (AI Denoise của Lightroom) — `autotone_gui.py` (dòng ~2914)

**Hiện:** Bật AI Denoise của Lightroom cho ảnh có ISO từ ngưỡng bên dưới.

**Đầy đủ:**

> Ảnh có ISO từ ngưỡng dưới trở lên được bật Denoise của Lightroom ngay sau khi áp thông số. Lightroom sẽ mở module Develop và chọn lần lượt từng ảnh đó để bật (Lightroom Classic 14.4 trở lên); Denoise chạy nền trong Lightroom, mỗi ảnh vài giây tuỳ card màn hình.

### (gợi ý) — `autotone_gui.py` (dòng ~3093)

**Hiện:** Phân tích ảnh rồi áp vào Lightroom.

**Đầy đủ:**

> Phân tích ảnh (ảnh đã có kết quả thì không đo lại) rồi tự áp vào Lightroom — cửa sổ tiến trình báo từng bước, xong thì báo lại.
> Ảnh Loại 1★, Denoise ảnh ISO cao: đặt trong Thiết lập (⚙).
> Đo lại cả buổi: ⋯ → Phân tích lại cả buổi.

### (gợi ý) — `autotone_gui.py` (dòng ~3139)

**Hiện:** Huỷ lần gửi mà Lightroom chưa nhận.

**Đầy đủ:**

> Lightroom chưa nhận lần gửi này (chưa mở, hoặc plugin không chạy).
> Huỷ để không còn job nằm chờ — lúc nào Lightroom mở lên cũng sẽ
> không áp nó nữa. Sau đó bấm Xử lý ảnh lại khi Lightroom đã sẵn sàng.

### (gợi ý) — `cot_thu_muc.py` (dòng ~235)

**Hiện:** Lightroom xuất ảnh rồi app retouch — một thao tác.

**Đầy đủ:**

> Lightroom xuất ảnh cỡ gốc rồi app retouch — một thao tác.
> Hộp thoại chọn: chất lượng JPEG, thư mục xuất, ảnh retouch ghi đâu, cache xem trước, retouch ngay trong lúc xuất hay sau khi xuất xong (có kiểm tài nguyên máy). Tiến độ ở bước 5 · Xử lý & xuất.

### (gợi ý) — `giao_dien.py` (dòng ~3722)

**Hiện:** Lọc theo số sao. Bấm lại đúng số sao để bỏ lọc.

**Đầy đủ:**

> Lọc theo số sao trong Lightroom — bấm ≥ / = / ≤ để đổi cách so, bấm lại đúng số sao để bỏ lọc. Chấm sao: bấm sao dưới ảnh, hoặc phím 0–5.

### (gợi ý) — `man_retouch.py` (dòng ~408)

**Hiện:** Lăn chuột: phóng to · Kéo: di chuyển · Nháy đúp: về lưới.
Giữ chuột (hoặc phím \): xem ảnh gốc.
← →: tấm trước / sau · 0: vừa khung · 1: 100%.

**Đầy đủ:**

> Kéo thanh ở bảng phải: ảnh lớn tính lại NGAY theo mức đó (bản xem trước). Bấm ✕ trên nhãn “Xem trước” để về bản trên đĩa.
> Lăn chuột: phóng to / thu nhỏ quanh con trỏ.
> Kéo: di chuyển ảnh đang phóng.
> Nháy đúp lên ảnh: về LƯỚI ẢNH (bấm một ô để mở to lại).
> So sánh: Sau · Trước | Sau cạnh nhau · Chia đôi (kéo vạch) — phóng / kéo một bên là bên kia theo.
> Giữ chuột trên ảnh (hoặc giữ phím \): xem ảnh GỐC.
> ← →: tấm trước / sau · 0: vừa khung · 1: 100% · M: vào mặt kế tiếp.
> Dải ảnh: Ctrl + bấm chọn thêm, Shift + bấm chọn một dãy — để Sync mức.

### Vào — `man_retouch.py` (dòng ~1072)

**Hiện:** Thư mục ảnh Lightroom đã xuất.

**Đầy đủ:**

> Thư mục Lightroom vừa Export ra — retouch lấy ảnh từ đây. Mở buổi nào thì tự theo thư mục Export của buổi đó.

### Ghi đè lên ảnh gốc — `man_retouch.py` (dòng ~1090)

**Hiện:** Ảnh retouch thay thế ảnh gốc (không hoàn tác được).

**Đầy đủ:**

> Không cần thư mục ra: ảnh retouch THAY THẾ ảnh gốc. Không lùi lại được — lúc bấm Chạy sẽ hỏi lại kèm số ảnh và đường dẫn.

### Tự retouch ảnh mới thêm vào — `man_retouch.py` (dòng ~1099)

**Hiện:** Tiếp tục theo dõi thư mục Vào và tự retouch ảnh mới chép vào.

**Đầy đủ:**

> Bật rồi bấm Chạy retouch: chạy xong app vẫn THEO DÕI thư mục Vào. Ảnh nào mới chép vào — kể cả trong lúc đang chạy — được tự retouch bằng MỨC CHUNG (các thanh ở thẻ Chung lúc bấm Chạy, không dùng mức riêng giới tính) rồi xuất ra, hoặc ghi đè nếu đang bật ghi đè. Ảnh có sẵn lúc bấm Chạy không bị tính là ảnh mới. Bấm Dừng để thôi theo dõi.

### Bỏ qua ảnh không có người — `man_retouch.py` (dòng ~1108)

**Hiện:** Ảnh không có khuôn mặt thì không retouch, chép nguyên bản.

**Đầy đủ:**

> Ảnh không thấy khuôn mặt nào (phong cảnh, đồ vật, trang trí, sân khấu trống) thì không chạy retouch — chép nguyên bản, đỡ tốn thời gian. Ảnh người quay lưng hoặc ở quá xa (không thấy mặt) cũng bị bỏ qua: cần retouch da tay / chân / thân ở những ảnh đó thì tắt ô này.

### (gợi ý) — `man_retouch.py` (dòng ~1162)

**Hiện:** Bộ mức retouch đã lưu. Chọn để áp, Lưu để lưu bảng hiện tại.

**Đầy đủ:**

> Bộ mức đã lưu (cả mức riêng theo nhóm mặt). Chọn = áp cho ảnh đang xem như vừa kéo; chưa có ảnh thì làm mức chung. Lưu = ghi bảng đang hiện thành preset (hỏi tên). Hộp thoại Xuất cũng chọn preset từ đây cho cả lượt ảnh Lightroom xuất ra.

### (gợi ý) — `man_retouch.py` (dòng ~1192)

**Hiện:** Kéo thanh để chỉnh ảnh đang xem. Reset về 0: tắt hết. Sync: chép mức sang các ảnh đang chọn.

**Đầy đủ:**

> Kéo thanh là chỉnh ẢNH ĐANG XEM (như Evoto) — ảnh lớn tính lại ngay. Mở thư mục mới thì mọi thanh ở 0; tự kéo tính năng muốn dùng.
> 
> Reset về 0: đưa mọi thanh của ảnh đang xem về 0.
> 
> Sync ảnh đã chọn: chép mức của ảnh đang xem sang các tấm đang chọn ở dải ảnh — Ctrl + bấm để chọn thêm, Shift + bấm để chọn một dãy, Ctrl+A chọn hết.
> 
> Lúc chạy, ảnh khác mức nhau thì tool chạy theo từng nhóm mức (mỗi nhóm một lượt).

### (gợi ý) — `man_retouch.py` (dòng ~1237)

**Hiện:** Đưa mọi thanh của ảnh đang xem về 0.

**Đầy đủ:**

> Đưa mọi thanh của ẢNH ĐANG XEM về 0 (tắt hết tính năng). Muốn reset nhiều ảnh thì Reset rồi bấm Sync.

### (gợi ý) — `man_retouch.py` (dòng ~1243)

**Hiện:** Chép mức của ảnh đang xem sang các ảnh đang chọn.

**Đầy đủ:**

> Chép mức của ảnh đang xem sang các tấm đang chọn ở dải ảnh (Ctrl / Shift + bấm để chọn nhiều tấm; Ctrl+A chọn hết).

### (gợi ý) — `man_retouch.py` (dòng ~1252)

**Hiện:** Phần cứng chạy retouch. auto: tự chọn (khuyên dùng).

**Đầy đủ:**

> auto: tự dùng card đồ hoạ nếu có. cuda: card NVIDIA. mps: Mac chip Apple. cpu: chỉ dùng CPU — chậm, nhưng máy nào cũng chạy.

### (gợi ý) — `man_retouch.py` (dòng ~1263)

**Hiện:** Số luồng chạy. 0 = tự chọn (khuyên dùng).

**Đầy đủ:**

> 0 = để tool tự dò theo số lõi và bộ nhớ còn trống — khuyên dùng. Ép một con số là tắt phần tự dò đó.

### (gợi ý) — `man_retouch.py` (dòng ~1280)

**Hiện:** Tự động: tool tự chọn (khuyên dùng). Tiết kiệm: cho máy yếu. Nhanh: dùng nhiều bộ nhớ hơn.

**Đầy đủ:**

> Tự động: tool tự đo máy rồi chọn — nên dùng. Tiết kiệm: một luồng, ô nhớ nhỏ nhất — cho máy yếu hoặc khi đang chạy việc khác. Nhanh: dám dùng nhiều bộ nhớ hơn.

### Làm lại cả ảnh đã có kết quả — `man_retouch.py` (dòng ~1287)

**Hiện:** Bật: làm lại cả ảnh đã có trong thư mục ra.

**Đầy đủ:**

> Mặc định tool bỏ qua ảnh đã có trong thư mục ra — chạy lại là đi tiếp từ chỗ dừng. Bật để làm lại từ đầu.

### (gợi ý) — `preset_ui.py` (dòng ~495)

**Hiện:** Xem trước cả lưới theo một preset Lightroom (không đổi ảnh trong catalog).

**Đầy đủ:**

> Chọn preset Lightroom để xem trước CẢ LƯỚI theo preset đó — Lightroom render thật (cần Lightroom đang mở). Không đổi ảnh trong catalog.

### (gợi ý) — `preset_ui.py` (dòng ~613)

**Hiện:** Lightroom dựng theo preset mọi ảnh của buổi.

**Đầy đủ:**

> Lightroom dựng theo preset MỌI ảnh của buổi (~0,5–1 giây / ảnh). Bình thường chỉ ảnh đang xem + trước / sau được dựng.

### (gợi ý) — `preset_ui.py` (dòng ~623)

**Hiện:** Áp preset đang chọn cho mọi ảnh của buổi (hoàn tác được).

**Đầy đủ:**

> Áp preset đang chọn vào catalog cho mọi ảnh RAW của buổi — đúng như chọn hết ảnh rồi bấm preset trong Lightroom. Có sổ để hoàn tác.

### (gợi ý) — `retouch_muc.py` (dòng ~221)

**Hiện:** Cần tải thư viện AI lần đầu chạy retouch.

**Đầy đủ:**

> Tính năng này cần thư viện AI (torch) — bản cài tải về lần đầu bấm “Chạy retouch”. Đặt mức trước cũng được; tải xong là chạy.

### (gợi ý) — `xu_ly_ui.py` (dòng ~224)

**Hiện:** Chế độ chạy Retouch. Tự động: khuyên dùng.

**Đầy đủ:**

> Chế độ chạy của Retouch. Tự động: tool tự đo máy rồi chọn — nên dùng. Nhanh: dám dùng nhiều bộ nhớ hơn. Tiết kiệm: một luồng, ô nhớ nhỏ nhất — cho máy yếu hoặc khi đang chạy việc khác.

### (gợi ý) — `xuat_ui.py` (dòng ~502)

**Hiện:** Lightroom xuất ảnh rồi app retouch — một thao tác.

**Đầy đủ:**

> Một thao tác: Lightroom xuất ảnh cỡ gốc → app retouch (ngay trong lúc xuất, hoặc sau khi xuất xong). Kích thước, không gian màu, metadata, quy tắc đặt tên vẫn theo thông số Export của Lightroom.

### (gợi ý) — `xuat_ui.py` (dòng ~508)

**Hiện:** Chất lượng JPEG (1–100).

**Đầy đủ:**

> 1–100 như hộp thoại Export của Lightroom. Ảnh giao khách thường 80–92; 100 nặng gấp đôi mà mắt không thấy khác.

### (gợi ý) — `xuat_ui.py` (dòng ~569)

**Hiện:** Dung lượng lưu ảnh xem trước retouch.

**Đầy đủ:**

> Ảnh xem trước retouch đã tính được lưu lại để mở lại thư mục / đang chạy mẻ vẫn xem được ngay. Vượt dung lượng thì tự xoá tấm lâu không xem nhất.
