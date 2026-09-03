#let project(title: "", author: "", logo: none, body) = {
  set page(
    paper: "a4",
    margin: (x: 2cm, top: 3.2cm, bottom: 2.5cm),
    
    // Header logic
    header: context {
      let page_num = counter(page).get().first()
      
      if page_num == 1 {
        if logo != none {
          align(center)[#image(logo, height: 2.2cm)]
        }
      } else {
        // Use straight quotes "" for empty strings or block syntax []
        grid(
          columns: (1fr, auto),
          align: (left + horizon, right + horizon),
          if logo != none { image(logo, height: 1.2cm) } else { [] },
          text(9pt, fill: luma(100), weight: "medium")[#title]
        )
        v(-0.2cm)
        line(length: 100%, stroke: 0.5pt + luma(200))
      }
    },
    
    // Footer logic
    footer: context {
      let page_num = counter(page).get().first()
      
      if page_num > 1 {
        align(center)[
          #text(9pt, fill: luma(100))[
            Page #counter(page).display("1 of 1", both: true)
          ]
        ]
      }
    }
  )

  set text(font: "Liberation Sans", size: 11pt)

  v(0.5cm)
  align(center)[
    #text(20pt, weight: "bold")[#title] \
    #v(0.3cm)
    #text(11pt, style: "italic", fill: luma(80))[#author]
  ]
  v(1cm)

  body
}