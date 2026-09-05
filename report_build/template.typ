
#let project(title: "", subtitle: "", author: "", logo: none, body) = {
  set page(
    paper: "a4",
    flipped: true, // Swaps orientation to landscape
    margin: (x: 2.5cm, top: 3.8cm, bottom: 2.2cm),
    
    // Header logic
    header: context {
      let page_num = counter(page).get().first()
      
      if page_num == 1 {
        // Empty on page 1 so only the center cover logo shows
        []
      } else {
        grid(
          columns: (1fr, auto),
          align: (left + horizon, right + horizon),
          if logo != none { image(logo, height: 1.0cm) } else { [] },
          align(right + horizon)[
            #text(9pt, fill: luma(100), weight: "medium")[#title]
            #if subtitle != "" [
              \
              #text(8pt, fill: luma(120), weight: "regular")[#subtitle]
            ]
          ]
        )
        v(-0.2cm)
        line(length: 100%, stroke: 0.5pt + luma(200))
      }
    },

    // Footer logic
    footer: context {
      let page_num = counter(page).get().first()
      
      if page_num > 1 {
        grid(
          columns: (1fr, auto),
          align: (left + horizon, right + horizon),
          text(9pt, fill: luma(100))[#author],
          text(9pt, fill: luma(100))[
            Page #counter(page).display("1 of 1", both: true)
          ]
        )
      }
    }
  )

  set text(font: "Montserrat", size: 11pt, lang: "sk")

  // Title Page Layout
  align(center + horizon)[
    #if logo != none {
      image(logo, height: 3cm)
      v(0.8cm)
    }
    
    #text(16pt, weight: "medium", fill: luma(120), tracking: 0.1em)[
      #upper("Report Online Monitoringu")
    ]
    #v(0.4cm)

    #text(26pt, weight: "bold")[#title]
    #if subtitle != "" [
      #v(0.5cm)
      #text(16pt, weight: "medium", fill: luma(100))[#subtitle]
    ]
    #v(0.8cm)
    #text(12pt, style: "italic", fill: luma(80))[#author]
  ]

  // Cover page break
  pagebreak()

  
  // // List of Charts / Figures
  // outline(
  //   title: [Zoznam grafov],
  //   target: figure.where(kind: image)
  // )

// List of Charts / Figures with custom text size
  [
    #set text(size: 9pt) // Adjust this value to your preferred size
    #outline(
      title: [Zoznam grafov],
      target: figure.where(kind: image)
    )
  ]  

  // Start main content on a fresh page after the outline
  pagebreak()

  // Main Document Content
  body

  // Signature Block at the end of the document
  v(1cm)
  align(right)[
    #block(width: 4cm)[
      #image("sign.svg", width: 100%)
      #v(-0.5cm)
      #line(length: 100%, stroke: 0.5pt + luma(150))
      #text(9pt, fill: luma(80))[#author]
    ]
  ]
}

#let fullpage-image(path, caption: none) = {
  pagebreak(weak: true)
  align(center + horizon)[
    #layout(size => {
      // Reserve space for caption text and vertical spacing
      let caption-space = if caption != none { 2.5cm } else { 0cm }
      let max-img-height = size.height - caption-space

      figure(
        image(path, height: max-img-height, fit: "contain"),
        caption: caption
      )
    })
  ]
  pagebreak(weak: true)
}